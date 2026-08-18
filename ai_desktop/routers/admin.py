"""超级管理员路由：用户管理与角色分配。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..aliyun_aigw import USE_MOCK, list_consumers
from ..database import get_db
from ..deps import ALL_ROLES, ROLE_KEY_ADMIN, ROLE_SKILLS_ADMIN, ROLE_SUPER_ADMIN, CurrentUser
from ..models import (
    KEY_APPROVED,
    KEY_PENDING,
    KEY_REJECTED,
    KEY_REVOKED,
    STATUS_PENDING,
    STATUS_PUBLISHED,
    ApiKey,
    Employee,
    Feedback,
    KeyUsage,
    Skill,
    SkillVersion,
)
from ..services.banners import (
    _parse_dt,
    create_banner_slide,
    delete_banner_slide,
    list_banner_slides,
    toggle_banner_slide,
)

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# 角色中文标签
ROLE_LABELS = {
    "skills_admin": "Skills 管理员",
    "key_admin": "密钥管理员",
    "super_admin": "超级管理员",
}


def _common_ctx(db: Session, request: Request) -> dict:
    pending_skills = db.query(SkillVersion).filter(
        SkillVersion.status == STATUS_PENDING).count()
    pending_keys = db.query(ApiKey).filter(ApiKey.status == KEY_PENDING).count()
    unread_feedback = db.query(Feedback).filter(Feedback.is_read.is_(False)).count()
    return {
        "current_user": request.state.current_user,
        "pending_reviews_count": pending_skills,
        "pending_key_count": pending_keys,
        "total_feedback": unread_feedback,  # 子导航「用户反馈」未读角标，全后台页常驻
    }


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_db)):
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限访问管理后台")

    ctx = _common_ctx(db, request)
    employees = db.query(Employee).order_by(Employee.name).all()

    # 统计
    total = len(employees)
    super_admins = sum(1 for e in employees if "super_admin" in e.roles_list)
    skills_admins = sum(1 for e in employees if "skills_admin" in e.roles_list)
    key_admins = sum(1 for e in employees if "key_admin" in e.roles_list)

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            **ctx,
            "page": "admin",
            "admin_subpage": "users",
            "employees": employees,
            "role_labels": ROLE_LABELS,
            "all_roles": ALL_ROLES,
            "counts": {
                "total": total,
                "super_admin": super_admins,
                "skills_admin": skills_admins,
                "key_admin": key_admins,
            },
        },
    )


# ---------- Skills 审核子页面 ----------

@router.get("/admin/skill-reviews", response_class=HTMLResponse)
def admin_skill_reviews(request: Request, db: Session = Depends(get_db)):
    """Skills 审核管理子页面（仅 skills_admin / super_admin）。"""
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SKILLS_ADMIN):
        raise HTTPException(403, "无权限访问 Skills 审核")

    ctx = _common_ctx(db, request)
    pending = (
        db.query(SkillVersion)
        .filter(SkillVersion.status == STATUS_PENDING)
        .order_by(SkillVersion.submitted_at.desc(), SkillVersion.id.desc())
        .all()
    )
    history = (
        db.query(SkillVersion)
        .filter(SkillVersion.status.in_(["published", "rejected"]))
        .filter(SkillVersion.decided_at.isnot(None))
        .order_by(SkillVersion.decided_at.desc())
        .all()
    )
    counts = {
        "pending": len(pending),
        "published": db.query(Skill)
        .filter(Skill.versions.any(SkillVersion.status == STATUS_PUBLISHED))
        .count(),
        "teams": db.query(Skill)
        .filter(Skill.owner_team.isnot(None))
        .distinct(Skill.owner_team)
        .count(),
    }

    return templates.TemplateResponse(
        request,
        "admin_skill_reviews.html",
        {
            **ctx,
            "page": "admin",
            "admin_subpage": "skill_reviews",
            "pending": pending,
            "history": history,
            "counts": counts,
        },
    )


# ---------- 密钥审核子页面 ----------

@router.get("/admin/key-reviews", response_class=HTMLResponse)
def admin_key_reviews(request: Request, db: Session = Depends(get_db)):
    """密钥审核管理子页面（仅 key_admin / super_admin）。"""
    user: CurrentUser = request.state.current_user
    if not (user.has_role(ROLE_KEY_ADMIN) or user.has_role(ROLE_SUPER_ADMIN)):
        raise HTTPException(403, "无权限访问密钥审核")
    is_super_admin = user.has_role(ROLE_SUPER_ADMIN)

    ctx = _common_ctx(db, request)
    pending_review = (
        db.query(ApiKey)
        .filter(ApiKey.status == KEY_PENDING)
        .order_by(ApiKey.created_at.asc())
        .all()
    )
    reviewed_history = (
        db.query(ApiKey)
        .filter(ApiKey.status.in_([KEY_APPROVED, KEY_REJECTED, KEY_REVOKED]))
        .order_by(ApiKey.reviewed_at.desc().nullslast())
        .all()
    )
    active_keys = (
        db.query(ApiKey)
        .filter(ApiKey.status == KEY_APPROVED)
        .order_by(ApiKey.reviewed_at.desc().nullslast())
        .all()
    )

    # 密钥分配时可选的 AI Gateway 消费组（网关不可达时为空，不影响审核）
    try:
        consumers = list_consumers()
    except Exception:  # noqa: BLE001
        consumers = []

    return templates.TemplateResponse(
        request,
        "admin_key_reviews.html",
        {
            **ctx,
            "page": "admin",
            "admin_subpage": "key_reviews",
            "can_review": True,
            "pending_review": pending_review,
            "reviewed_history": reviewed_history,
            "active_keys": active_keys,
            "consumers": consumers,
            "is_super_admin": is_super_admin,
        },
    )


# ---------- API Key 用量分析子页面 ----------

def _month_list(n: int = 6) -> list[str]:
    """最近 n 个自然月（含当月），升序，格式 YYYY-MM。"""
    from datetime import datetime

    today = datetime.utcnow()
    months: list[str] = []
    y, m = today.year, today.month
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(months))


@router.get("/admin/api-usage", response_class=HTMLResponse)
def admin_api_usage(
    request: Request,
    month: str | None = None,
    page: int = 1,
    q: str = "",
    filter: str | None = None,  # "over" | "low" | None
    db: Session = Depends(get_db),
):
    """API Key 月度用量分析（仅超级管理员）。

    展示「每个月已分配密钥的用户」的：分配额度、已使用、使用率，
    便于后续根据使用情况调整配额。支持姓名搜索、高/低水位过滤与分页。
    """
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限访问用量分析")

    ctx = _common_ctx(db, request)
    months = _month_list(6)
    current = month or months[-1]

    # 已分配密钥（同一用户可能有多条，按用户去重，取最新一条）
    approved = (
        db.query(ApiKey)
        .filter(ApiKey.status == KEY_APPROVED)
        .order_by(ApiKey.applicant_id, ApiKey.reviewed_at.desc().nullslast())
        .all()
    )
    key_by_user: dict[str, ApiKey] = {}
    for k in approved:
        key_by_user.setdefault(k.applicant_id, k)

    # 该月已有的用量记录
    usage_by_user: dict[str, KeyUsage] = {
        u.user_id: u
        for u in db.query(KeyUsage).filter(KeyUsage.month == current).all()
    }

    rows = []
    for uid, k in key_by_user.items():
        rec = usage_by_user.get(uid)
        if rec is not None:
            allocated = rec.allocated
            used = rec.used
            dept = rec.department or "—"
            is_demo = rec.is_demo
        else:
            # 有密钥但本月暂无用量记录：以默认额度占位，已用计 0
            allocated = 1000
            used = 0
            dept = "—"
            is_demo = False
        rate = (used / allocated) if allocated > 0 else 0.0
        rate_pct = int(round(min(rate, 1.0) * 100))
        rows.append(
            {
                "user_id": uid,
                "user_name": k.applicant_name or uid,
                "department": dept,
                "consumer_name": k.consumer_name or "—",
                "quota_rule_name": k.quota_rule_name or "—",
                "allocated": allocated,
                "used": used,
                "rate": rate,
                "rate_pct": rate_pct,
                "over_threshold": rate >= 0.9,
                "low_usage": allocated > 0 and rate <= 0.2,
                "has_record": rec is not None,
                "is_demo": is_demo,
            }
        )
    # 排序：使用率高的在前，便于优先关注
    rows.sort(key=lambda r: r["rate"], reverse=True)

    # ── 月份总览（过滤前，供顶部计数卡）──
    total_allocated = sum(r["allocated"] for r in rows)
    total_used = sum(r["used"] for r in rows)
    avg_rate = (total_used / total_allocated) if total_allocated > 0 else 0.0
    user_count = len(rows)
    over_count = sum(1 for r in rows if r["over_threshold"])
    low_count = sum(1 for r in rows if r["low_usage"])

    # ── 应用搜索 + 高/低水位过滤 ──
    q_norm = (q or "").strip()
    if q_norm:
        ql = q_norm.lower()
        rows = [
            r for r in rows
            if ql in (r["user_name"] or "").lower()
            or ql in (r["user_id"] or "").lower()
        ]
    if filter == "over":
        rows = [r for r in rows if r["over_threshold"]]
    elif filter == "low":
        rows = [r for r in rows if r["low_usage"]]

    # ── 分页（每页 10 条）──
    page_size = 10
    total_rows = len(rows)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]

    return templates.TemplateResponse(
        request,
        "admin_api_usage.html",
        {
            **ctx,
            "page": "admin",
            "admin_subpage": "api_usage",
            "months": months,
            "current_month": current,
            "rows": page_rows,
            "summary": {
                "user_count": user_count,
                "total_allocated": total_allocated,
                "total_used": total_used,
                "avg_rate": int(round(avg_rate * 100)),
                "over_count": over_count,
                "low_count": low_count,
            },
            "page_num": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total_rows": total_rows,
            "q": q_norm,
            "active_filter": filter or "",
            "use_mock": USE_MOCK,
        },
    )


@router.post("/api/admin/api-usage")
def api_update_api_usage(
    request: Request,
    user_id: str = Form(...),
    month: str = Form(...),
    allocated: int = Form(...),
    used: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """调整某用户某月的分配额度（或用量），便于后续配额调整。

    记录不存在时按该用户最新已分配密钥自动补全后新建。
    """
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限访问用量分析")
    if allocated < 0 or (used is not None and used < 0):
        raise HTTPException(400, "额度 / 用量不能为负")

    uid = user_id.strip()
    month = month.strip()
    if not uid or not month:
        raise HTTPException(400, "user_id 与 month 均不能为空")

    rec = (
        db.query(KeyUsage)
        .filter(KeyUsage.user_id == uid, KeyUsage.month == month)
        .first()
    )
    if rec is None:
        k = (
            db.query(ApiKey)
            .filter(ApiKey.applicant_id == uid, ApiKey.status == KEY_APPROVED)
            .order_by(ApiKey.reviewed_at.desc().nullslast())
            .first()
        )
        rec = KeyUsage(
            user_id=uid,
            user_name=k.applicant_name if k else uid,
            department="—",
            month=month,
        )
        db.add(rec)
    rec.allocated = allocated
    if used is not None:
        rec.used = used
    rec.is_demo = False  # 人工调整后视为真实录入
    db.commit()
    return {
        "ok": True,
        "user_id": uid,
        "month": month,
        "allocated": rec.allocated,
        "used": rec.used,
        "rate_pct": rec.rate_pct,
    }


# ---------- API ----------

class RoleUpdate(BaseModel):
    roles: list[str]


class EmployeeCreate(BaseModel):
    id: str
    name: str
    department: str = ""
    roles: list[str] = []


@router.get("/api/employees/{emp_id}")
def employee_detail(emp_id: str, db: Session = Depends(get_db)):
    emp = db.get(Employee, emp_id)
    if not emp:
        raise HTTPException(404, "员工不存在")
    return {
        "id": emp.id,
        "name": emp.name,
        "department": emp.department,
        "roles": emp.roles_list,
        "is_test_data": emp.is_test_data,
        "role_labels": ROLE_LABELS,
    }


@router.post("/api/employees/{emp_id}/roles")
def update_roles(
    emp_id: str, body: RoleUpdate, request: Request,
    db: Session = Depends(get_db)
):
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限修改角色")

    emp = db.get(Employee, emp_id)
    if not emp:
        raise HTTPException(404, "员工不存在")

    # 过滤非法角色
    valid_roles = [r for r in body.roles if r in ALL_ROLES]
    emp.set_roles(valid_roles)
    db.commit()

    return {"ok": True, "roles": valid_roles, "role_label": emp.role_label}


@router.post("/api/employees")
def create_employee(
    body: EmployeeCreate, request: Request,
    db: Session = Depends(get_db)
):
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限创建用户")

    # 检查工号是否已存在
    existing = db.get(Employee, body.id)
    if existing:
        raise HTTPException(409, f"工号 {body.id} 已存在")

    # 过滤非法角色
    valid_roles = [r for r in body.roles if r in ALL_ROLES]

    emp = Employee(
        id=body.id,
        name=body.name,
        department=body.department,
        is_test_data=False,
    )
    emp.set_roles(valid_roles)
    db.add(emp)
    db.commit()

    return {"ok": True, "id": emp.id, "name": emp.name}


# =========================================================================== #
# 首页轮播（自定义幻灯片）管理
# =========================================================================== #
@router.get("/admin/banners", response_class=HTMLResponse)
def admin_banners(request: Request, db: Session = Depends(get_db)):
    """首页轮播管理页（仅超级管理员）。"""
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限访问")

    ctx = _common_ctx(db, request)
    slides = list_banner_slides(db)
    return templates.TemplateResponse(
        request,
        "admin_banners.html",
        {
            **ctx,
            "page": "admin",
            "admin_subpage": "banners",
            "slides": slides,
            "now": datetime.utcnow(),
        },
    )


@router.post("/admin/banners")
def admin_banners_create(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    link: str = Form(""),
    link_text: str = Form(""),
    accent: str = Form("orange"),
    validity: str = Form("permanent"),
    start_at: str = Form(""),
    end_at: str = Form(""),
    db: Session = Depends(get_db),
):
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限操作")
    if not title.strip() or not content.strip():
        raise HTTPException(400, "标题与内容必填")

    # 有效期：仅当选择「指定时间段」时才解析起止时间
    s_start = s_end = None
    if validity == "range":
        s_start = _parse_dt(start_at)
        s_end = _parse_dt(end_at)
        if s_start is None or s_end is None:
            raise HTTPException(400, "请完整填写有效的开始与结束时间")
        if s_end < s_start:
            raise HTTPException(400, "结束时间不能早于开始时间")

    create_banner_slide(
        db,
        title=title,
        content=content,
        link=link,
        link_text=link_text,
        accent=accent,
        is_active=True,
        start_at=s_start,
        end_at=s_end,
    )
    return RedirectResponse(url="/admin/banners", status_code=303)


@router.post("/admin/banners/{slide_id}/delete")
def admin_banners_delete(slide_id: int, request: Request,
    db: Session = Depends(get_db)):
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限操作")
    delete_banner_slide(db, slide_id)
    return RedirectResponse(url="/admin/banners", status_code=303)


@router.post("/admin/banners/{slide_id}/toggle")
def admin_banners_toggle(slide_id: int, request: Request,
    db: Session = Depends(get_db)):
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限操作")
    toggle_banner_slide(db, slide_id)
    return RedirectResponse(url="/admin/banners", status_code=303)
