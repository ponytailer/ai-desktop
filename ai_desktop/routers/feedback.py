"""用户反馈：提交（任意登录用户）与查看（仅超级管理员）。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import ROLE_SUPER_ADMIN, CurrentUser
from ..models import Feedback

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class FeedbackCreate(BaseModel):
    content: str


class FeedbackReadBody(BaseModel):
    ids: list[int] = []


@router.post("/api/feedback")
def submit_feedback(body: FeedbackCreate, request: Request, db: Session = Depends(get_db)):
    """任意登录用户提交反馈，自动关联当前用户的工号与姓名。"""
    user: CurrentUser = request.state.current_user
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(400, "反馈内容不能为空")

    fb = Feedback(
        content=content,
        employee_id=user.id,
        employee_name=user.name,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return {"ok": True, "id": fb.id}


@router.post("/api/feedback/{fb_id}/read")
def mark_feedback_read(fb_id: int, request: Request, db: Session = Depends(get_db)):
    """单条标记已读（仅 super_admin）。"""
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限操作")

    fb = db.query(Feedback).filter(Feedback.id == fb_id).first()
    if not fb:
        raise HTTPException(404, "反馈不存在")
    fb.is_read = True
    db.commit()
    return {"ok": True, "id": fb.id}


@router.post("/api/feedback/read")
def mark_feedback_read_batch(
    body: FeedbackReadBody, request: Request, db: Session = Depends(get_db)
):
    """批量标记已读（仅 super_admin）。"""
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限操作")

    ids = body.ids or []
    if not ids:
        return {"ok": True, "count": 0}
    db.query(Feedback).filter(Feedback.id.in_(ids)).update(
        {Feedback.is_read: True}, synchronize_session=False
    )
    db.commit()
    return {"ok": True, "count": len(ids)}


@router.get("/admin/feedback", response_class=HTMLResponse)
def admin_feedback(request: Request, db: Session = Depends(get_db)):
    """用户反馈管理子页面（仅 super_admin）。"""
    user: CurrentUser = request.state.current_user
    if not user.has_role(ROLE_SUPER_ADMIN):
        raise HTTPException(403, "无权限访问用户反馈")

    from .admin import _common_ctx

    ctx = _common_ctx(db, request)
    feedbacks = (
        db.query(Feedback)
        .order_by(Feedback.created_at.desc())
        .all()
    )
    unread = sum(1 for f in feedbacks if not f.is_read)

    return templates.TemplateResponse(
        request,
        "admin_feedback.html",
        {
            **ctx,
            "page": "admin",
            "admin_subpage": "feedback",
            "feedbacks": feedbacks,
            "total": len(feedbacks),
            "unread_count": unread,
            "total_feedback": unread,  # 子导航 badge 显示未读数
        },
    )
