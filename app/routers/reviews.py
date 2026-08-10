"""审核 API + 弹窗所需的 payload。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Skill,
    SkillVersion,
    STATUS_PENDING,
    STATUS_PUBLISHED,
    STATUS_REJECTED,
)
from ..deps import CurrentUser

router = APIRouter()


@router.get("/api/reviews/{version_id}")
def review_payload(version_id: int, db: Session = Depends(get_db)):
    v = db.get(SkillVersion, version_id)
    if not v:
        raise HTTPException(404)
    return {
        "id": v.id,
        "name": v.skill.name,
        "version": v.version,
        "summary": v.summary,
        "detail": v.detail,
        "changelog": v.changelog,
        "status": v.status,
        "status_label": v.status_label,
        "scope": v.scope,
        "scope_label": v.scope_label,
        "tags": v.tags_list,
        "category": v.skill.category,
        "icon": v.skill.icon,
        "accent_color": v.skill.accent_color,
        "submission_source": "外部来源",
        "submitted_by": v.submitted_by,
        "submitted_at": v.submitted_at.strftime("%Y-%m-%d") if v.submitted_at else "",
        "attachment_size_human": v.size_human,
    }


@router.post("/api/reviews/{version_id}/decide")
def decide_review(
    version_id: int,
    request: Request,
    decision: str = Form(...),        # "approve" / "reject"
    note: str = Form(""),             # 审核意见（拒绝时建议必填）
    feature_badge: str = Form("false"),  # 仅审核通过时可勾
    db: Session = Depends(get_db),
):
    user: CurrentUser = request.state.current_user
    v = db.get(SkillVersion, version_id)
    if not v:
        raise HTTPException(404)
    if v.status != STATUS_PENDING:
        raise HTTPException(400, "当前状态不允许审核")

    if decision == "approve":
        # 同一 skill 之前的 published 版本标记为 superseded
        for old in v.skill.versions:
            if old.id != v.id and old.status == STATUS_PUBLISHED:
                old.status = "superseded"
        v.status = STATUS_PUBLISHED
        v.featured_badge = feature_badge == "true"
        # 同步 Skill 主表统计
        v.skill.short_description = v.summary
        v.skill.is_featured = bool(v.featured_badge)
    elif decision == "reject":
        if not note.strip():
            raise HTTPException(400, "拒绝时必须填写审核意见")
        v.status = STATUS_REJECTED
    else:
        raise HTTPException(400, "decision 必须是 approve / reject")

    v.decision_note = note
    v.decided_by = user.name
    v.decided_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "status": v.status}
