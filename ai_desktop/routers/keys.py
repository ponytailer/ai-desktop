"""密钥管理：页面路由 + API。"""
from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..aliyun_aigw import list_consumers, list_quota_rules
from ..database import get_db
from ..deps import ROLE_KEY_ADMIN, ROLE_SKILLS_ADMIN, ROLE_SUPER_ADMIN, CurrentUser
from ..models import (
    KEY_APPROVED,
    KEY_PENDING,
    KEY_REJECTED,
    KEY_REVOKED,
    STATUS_PENDING,
    ApiKey,
    SkillVersion,
)

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# --------- 工具 ---------

def _generate_api_key() -> str:
    """生成一个假密钥（后续对接阿里云时替换）。"""
    return "sk-" + secrets.token_hex(16)


def _can_review_key(user: CurrentUser) -> bool:
    return user.has_role(ROLE_KEY_ADMIN)


# --------- 页面 ---------

@router.get("/keys", response_class=HTMLResponse)
def keys_page(request: Request, db: Session = Depends(get_db)):
    user: CurrentUser = request.state.current_user
    # 当前用户的申请
    my_keys = (
        db.query(ApiKey)
        .filter(ApiKey.applicant_id == user.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )

    counts = {
        "all": len(my_keys),
        "pending": sum(1 for k in my_keys if k.status == KEY_PENDING),
        "approved": sum(1 for k in my_keys if k.status == KEY_APPROVED),
        "rejected": sum(1 for k in my_keys if k.status == KEY_REJECTED)
    }

    # 当前用户是否已有在用密钥
    has_active_key = any(k.status == KEY_APPROVED for k in my_keys)

    # 当前用户是否具有任何管理角色（用于显示跳转提示）
    user_has_admin_role = (
        user.has_role(ROLE_KEY_ADMIN)
        or user.has_role(ROLE_SUPER_ADMIN)
        or user.has_role(ROLE_SKILLS_ADMIN)
    )

    pending_skills = db.query(SkillVersion).filter(SkillVersion.status == STATUS_PENDING).count()
    pending_keys = db.query(ApiKey).filter(ApiKey.status == KEY_PENDING).count()

    return templates.TemplateResponse(
        request,
        "keys.html",
        {
            "page": "keys",
            "current_user": user,
            "my_keys": my_keys,
            "counts": counts,
            "has_active_key": has_active_key,
            "user_has_admin_role": user_has_admin_role,
            "pending_reviews_count": pending_skills,
            "pending_key_count": pending_keys,
        },
    )


def _pending_skills_count(db: Session) -> int:
    return db.query(SkillVersion).filter(SkillVersion.status == STATUS_PENDING).count()


# --------- API ---------

@router.post("/api/keys/apply")
def apply_key(
    request: Request,
    purpose: str = Form(...),
    db: Session = Depends(get_db),
):
    """申请 API Key。"""
    user: CurrentUser = request.state.current_user
    # 检查是否已有在用密钥
    active = (
        db.query(ApiKey)
        .filter(ApiKey.applicant_id == user.id, ApiKey.status == KEY_APPROVED)
        .first()
    )
    if active:
        raise HTTPException(400, "您已有在用的 API Key，无法重复申请")

    purpose = purpose.strip()
    if len(purpose) < 5:
        raise HTTPException(400, "请填写至少 5 个字的申请用途")

    key = ApiKey(
        applicant_id=user.id,
        applicant_name=user.name,
        purpose=purpose,
        status=KEY_PENDING,
    )
    db.add(key)
    db.commit()
    return {"ok": True, "id": key.id, "status": key.status}


@router.post("/api/keys/{key_id}/approve")
def approve_key(
    request: Request,
    key_id: int,
    note: str = Form(""),
    consumer_id: str = Form(""),
    quota_rule_id: str = Form(""),
    db: Session = Depends(get_db),
):
    """审核通过并分配密钥（可绑定一个 AI Gateway 消费组与配额规则）。"""
    user: CurrentUser = request.state.current_user
    if not _can_review_key(user):
        raise HTTPException(403, "无权限：需要密钥管理员角色")

    k = db.get(ApiKey, key_id)
    if not k:
        raise HTTPException(404, "申请记录不存在")
    if k.status != KEY_PENDING:
        raise HTTPException(400, f"当前状态「{k.status_label}」不允许审核")

    consumer_id = consumer_id.strip()
    consumer_name = ""
    if consumer_id:
        # 最佳努力：尝试解析消费组名称用于展示（网关不可达时仅存 ID）
        try:
            cons = list_consumers()
            match = next(
                (c for c in cons if str(c.get("consumerId")) == consumer_id), None
            )
            consumer_name = match.get("name", "") if match else ""
        except Exception:  # noqa: BLE001
            consumer_name = ""

    quota_rule_id = quota_rule_id.strip()
    quota_rule_name = ""
    if quota_rule_id:
        try:
            rules = list_quota_rules()
            rmatch = next(
                (r for r in rules if str(r.get("ruleId")) == quota_rule_id), None
            )
            quota_rule_name = rmatch.get("ruleName", "") if rmatch else ""
        except Exception:  # noqa: BLE001
            quota_rule_name = ""

    k.api_key_value = _generate_api_key()
    k.status = KEY_APPROVED
    k.reviewed_by = user.name
    k.reviewed_at = datetime.utcnow()
    k.review_note = note.strip()
    k.consumer_id = consumer_id or None
    k.consumer_name = consumer_name or None
    k.quota_rule_id = quota_rule_id or None
    k.quota_rule_name = quota_rule_name or None
    db.commit()
    return {
        "ok": True,
        "status": k.status,
        "api_key": k.api_key_value,
        "consumer_id": k.consumer_id,
        "consumer_name": k.consumer_name,
        "quota_rule_id": k.quota_rule_id,
        "quota_rule_name": k.quota_rule_name,
    }


@router.post("/api/keys/{key_id}/reject")
def reject_key(
    request: Request,
    key_id: int,
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    """拒绝密钥申请。"""
    user: CurrentUser = request.state.current_user
    if not _can_review_key(user):
        raise HTTPException(403, "无权限：需要密钥管理员角色")

    k = db.get(ApiKey, key_id)
    if not k:
        raise HTTPException(404, "申请记录不存在")
    if k.status != KEY_PENDING:
        raise HTTPException(400, f"当前状态「{k.status_label}」不允许审核")

    if not note.strip():
        raise HTTPException(400, "拒绝时必须填写说明")

    k.status = KEY_REJECTED
    k.reviewed_by = user.name
    k.reviewed_at = datetime.utcnow()
    k.review_note = note.strip()
    db.commit()
    return {"ok": True, "status": k.status}


@router.post("/api/keys/{key_id}/revoke")
def revoke_key(
    request: Request,
    key_id: int,
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    """吊销已分配的密钥（仅本人或管理员）。需填写吊销原因。"""
    user: CurrentUser = request.state.current_user
    k = db.get(ApiKey, key_id)
    if not k:
        raise HTTPException(404, "申请记录不存在")
    if k.status != KEY_APPROVED:
        raise HTTPException(400, "只有已分配的密钥可以吊销")
    is_owner = k.applicant_id == user.id
    is_admin = _can_review_key(user)
    if not is_owner and not is_admin:
        raise HTTPException(403, "无权限")

    if not reason.strip():
        raise HTTPException(400, "请填写吊销原因")

    k.status = KEY_REVOKED
    k.reviewed_by = user.name
    k.reviewed_at = datetime.utcnow()
    k.review_note = reason.strip()
    db.commit()
    return {"ok": True, "status": k.status}
