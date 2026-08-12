"""超级管理员路由：用户管理与角色分配。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..aliyun_aigw import list_consumers
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
    Skill,
    SkillVersion,
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
        .order_by(SkillVersion.submitted_at.asc())
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
