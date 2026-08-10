"""阿里云 AI Gateway 对接：消费者管理 + 积分用量看板。

页面：
- GET /aigw              积分用量看板（首页，含两个图表）
- GET /aigw/consumers    消费者管理（列表 / 创建 / 删除）

API：
- GET    /api/aigw/consumers              列出消费者
- POST   /api/aigw/consumers              创建消费者
- DELETE /api/aigw/consumers/{id}         删除消费者
- GET    /api/aigw/quota/usage            获取积分用量（驱动图表）
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..aliyun_aigw import (
    USE_MOCK,
    create_consumer,
    create_quota_rule,
    delete_consumer,
    delete_quota_rule,
    get_quota_usage,
    list_consumers,
    list_quota_rules,
    update_quota_rule,
)
from ..database import get_db
from ..deps import ROLE_SUPER_ADMIN, CurrentUser
from ..models import KEY_APPROVED, ApiKey

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _require_super_admin(request: Request) -> CurrentUser:
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "需要超级管理员权限")
    return user


# --------- 页面 ---------

@router.get("/aigw", response_class=HTMLResponse)
def aigw_dashboard(request: Request, db: Session = Depends(get_db)):
    """积分用量看板（首页）：任意登录用户查看自己的使用情况。"""
    user: CurrentUser = request.state.current_user
    return templates.TemplateResponse(
        request,
        "aigw_dashboard.html",
        {
            "page": "aigw_dashboard",
            "current_user": user,
            "use_mock": USE_MOCK,
        },
    )


@router.get("/aigw/consumers", response_class=HTMLResponse)
def aigw_consumers_redirect():
    """消费者管理已并入管理后台-密钥管理，重定向到密钥审核页。"""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/admin/key-reviews", status_code=302)


# --------- API ---------

@router.get("/api/aigw/consumers")
def api_list_consumers(request: Request):
    _require_super_admin(request)
    try:
        items = list_consumers()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"获取消费者列表失败：{exc}") from exc
    return {"ok": True, "items": items, "mock": USE_MOCK}


@router.post("/api/aigw/consumers")
def api_create_consumer(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    gateway_type: str = Form("AI"),
):
    _require_super_admin(request)
    name = name.strip()
    if not name:
        raise HTTPException(400, "消费者名称不能为空")
    try:
        result = create_consumer(name, description=description.strip(), gateway_type=gateway_type)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"创建消费者失败：{exc}") from exc
    return {"ok": True, "result": result, "mock": USE_MOCK}


@router.delete("/api/aigw/consumers/{consumer_id}")
def api_delete_consumer(request: Request, consumer_id: str):
    _require_super_admin(request)
    try:
        result = delete_consumer(consumer_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"删除消费者失败：{exc}") from exc
    return {"ok": True, "result": result, "mock": USE_MOCK}


def _own_consumer(db: Session, user_id: str) -> dict | None:
    """返回当前用户已分配的密钥所绑定的消费组（consumerId / name）。"""
    k = (
        db.query(ApiKey)
        .filter(
            ApiKey.applicant_id == user_id,
            ApiKey.status == KEY_APPROVED,
            ApiKey.consumer_id.isnot(None),
        )
        .order_by(ApiKey.reviewed_at.desc().nullslast())
        .first()
    )
    if not k:
        return None
    return {"consumer_id": k.consumer_id, "consumer_name": k.consumer_name}


@router.get("/api/aigw/quota/usage")
def api_quota_usage(
    request: Request,
    subject_id: str | None = None,
    db: Session = Depends(get_db),
):
    """获取积分用量。

    - 普通用户：展示自己已分配密钥绑定的消费组用量（subject_id 被忽略）。
    - 超级管理员：可传 ?subject_id= 查看任意消费组；不传则同样看自己的。
    """
    user: CurrentUser = request.state.current_user
    is_admin = user.has_role(ROLE_SUPER_ADMIN)

    if subject_id and is_admin:
        subject = subject_id.strip()
        allocated = True
        is_self = False
    else:
        own = _own_consumer(db, user.id)
        subject = own["consumer_id"] if own else None
        allocated = own is not None
        is_self = True

    if not subject:
        if USE_MOCK:
            # 演示模式：无消费组也用派生 subject 渲染示例图表
            subject = f"cs-mock-{user.id}"
            allocated = False
        else:
            return {
                "ok": False,
                "allocated": False,
                "is_self": is_self,
                "message": "您尚未分配消费组，请联系管理员为您分配密钥并绑定消费组。",
            }

    try:
        data = get_quota_usage(subject)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"获取积分用量失败：{exc}") from exc
    return {
        "ok": True,
        "usage": data,
        "subject_id": subject,
        "allocated": allocated,
        "is_self": is_self,
        "mock": USE_MOCK,
    }


# --------- 配额规则 CRUD（仅超级管理员）---------

@router.get("/api/aigw/quota-rules")
def api_list_quota_rules(request: Request):
    _require_super_admin(request)
    try:
        items = list_quota_rules()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"获取配额规则失败：{exc}") from exc
    return {"ok": True, "items": items, "mock": USE_MOCK}


@router.post("/api/aigw/quota-rules")
def api_create_quota_rule(
    request: Request,
    rule_name: str = Form(...),
    quota_dimension: str = Form("token"),
    quota_limit: int = Form(...),
    period_type: str = Form("day"),
    window_alignment: str = Form("calendar"),
    timezone: str = Form("UTC+8"),
    consumer_ids: list[str] | None = Form(None),
):
    _require_super_admin(request)
    rule_name = rule_name.strip()
    if not rule_name:
        raise HTTPException(400, "规则名称不能为空")
    if quota_limit <= 0:
        raise HTTPException(400, "配额额度必须大于 0")
    try:
        result = create_quota_rule(
            rule_name,
            quota_dimension,
            quota_limit,
            period_type=period_type,
            window_alignment=window_alignment,
            timezone=timezone,
            consumer_ids=consumer_ids,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"创建配额规则失败：{exc}") from exc
    return {"ok": True, "result": result, "mock": USE_MOCK}


@router.put("/api/aigw/quota-rules/{rule_id}")
def api_update_quota_rule(
    request: Request,
    rule_id: str,
    rule_name: str | None = Form(None),
    quota_limit: int | None = Form(None),
    add_ids: list[str] | None = Form(None),
    remove_ids: list[str] | None = Form(None),
):
    _require_super_admin(request)
    try:
        result = update_quota_rule(
            rule_id,
            rule_name=rule_name,
            quota_limit=quota_limit,
            add_ids=add_ids,
            remove_ids=remove_ids,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"更新配额规则失败：{exc}") from exc
    return {"ok": True, "result": result, "mock": USE_MOCK}


@router.delete("/api/aigw/quota-rules/{rule_id}")
def api_delete_quota_rule(request: Request, rule_id: str):
    _require_super_admin(request)
    try:
        result = delete_quota_rule(rule_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"删除配额规则失败：{exc}") from exc
    return {"ok": True, "result": result, "mock": USE_MOCK}


@router.post("/api/aigw/consumers/{consumer_id}/quota")
def api_bind_consumer_quota(
    request: Request,
    consumer_id: str,
    rule_id: str = Form(...),
    rule_name: str = Form(""),
    quota_limit: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """批量修改某消费组内所有人（绑定该 consumer 的全部密钥/用户）的配额。

    - 阿里云侧：可选调整规则总额度，并将该 consumer 绑定到目标配额规则（addIds）。
    - 本地：把该 consumer 下所有 ApiKey 的 quota_rule_id / quota_rule_name 统一更新。
    """
    _require_super_admin(request)
    consumer_id = consumer_id.strip()
    rule_id = rule_id.strip()
    if not consumer_id or not rule_id:
        raise HTTPException(400, "consumer_id 与 rule_id 均不能为空")

    if quota_limit is not None and quota_limit > 0:
        try:
            update_quota_rule(rule_id, quota_limit=quota_limit)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"更新配额额度失败：{exc}") from exc
    try:
        update_quota_rule(rule_id, add_ids=[consumer_id])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"绑定消费组到配额规则失败：{exc}") from exc

    name = rule_name.strip() or rule_id
    affected = db.query(ApiKey).filter(ApiKey.consumer_id == consumer_id).all()
    for k in affected:
        k.quota_rule_id = rule_id
        k.quota_rule_name = name
    db.commit()
    return {
        "ok": True,
        "affected_keys": len(affected),
        "consumer_id": consumer_id,
        "rule_id": rule_id,
        "quota_rule_name": name,
        "mock": USE_MOCK,
    }
