"""个人工作看板：Todo 待办事项 CRUD。

- GET    /api/todos          当前用户列表（未完成在前，完成沉底）
- POST   /api/todos          新增（标题 1~100 字）
- PATCH  /api/todos/{id}     toggle 完成状态 / 改标题
- DELETE /api/todos/{id}     删除（仅本人）
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TodoItem

router = APIRouter()

MAX_TITLE_LEN = 100


class TodoPatch(BaseModel):
    done: bool | None = None
    title: str | None = None
    due_at: str | None = None  # ISO 字符串；"" 表示清空，None 表示不改


def _parse_due(raw: str | None) -> datetime | None:
    """解析 datetime-local 值（YYYY-MM-DDTHH:MM）；空则 None，非法 400。"""
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise HTTPException(400, "预期完成时间格式不正确") from None


def _serialize(item: TodoItem) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "done": item.done,
        "sort_order": item.sort_order,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "due_at": item.due_at.isoformat() if item.due_at else None,
    }


def _get_own(db: Session, user_id: str, item_id: int) -> TodoItem:
    item = db.get(TodoItem, item_id)
    if not item or item.user_id != user_id:
        raise HTTPException(404, "待办不存在")
    return item


@router.get("/api/todos")
def list_todos(request: Request, db: Session = Depends(get_db)):
    """列表：未完成按创建时间新→旧，已完成按完成时间新→旧沉底。"""
    user = request.state.current_user
    items = (
        db.query(TodoItem)
        .filter(TodoItem.user_id == user.id)
        .order_by(
            TodoItem.done.asc(),
            func.coalesce(TodoItem.completed_at, TodoItem.created_at).desc(),
        )
        .all()
    )
    return {"ok": True, "items": [_serialize(i) for i in items]}


@router.post("/api/todos")
def create_todo(
    request: Request,
    title: str = Form(...),
    due_at: str = Form(None),
    db: Session = Depends(get_db),
):
    user = request.state.current_user
    title = (title or "").strip()
    if not title:
        raise HTTPException(400, "待办内容不能为空")
    if len(title) > MAX_TITLE_LEN:
        raise HTTPException(400, f"待办内容不能超过 {MAX_TITLE_LEN} 字")

    max_order = (
        db.query(func.max(TodoItem.sort_order))
        .filter(TodoItem.user_id == user.id)
        .scalar()
        or 0
    )
    item = TodoItem(
        user_id=user.id,
        title=title,
        done=False,
        sort_order=max_order + 1,
        due_at=_parse_due(due_at),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"ok": True, "item": _serialize(item)}


@router.patch("/api/todos/{item_id}")
def patch_todo(
    item_id: int,
    payload: TodoPatch,
    request: Request,
    db: Session = Depends(get_db),
):
    user = request.state.current_user
    item = _get_own(db, user.id, item_id)

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(400, "待办内容不能为空")
        if len(title) > MAX_TITLE_LEN:
            raise HTTPException(400, f"待办内容不能超过 {MAX_TITLE_LEN} 字")
        item.title = title

    if payload.done is not None and payload.done != item.done:
        item.done = payload.done
        item.completed_at = datetime.now() if payload.done else None

    if payload.due_at is not None:
        item.due_at = _parse_due(payload.due_at)

    db.commit()
    db.refresh(item)
    return {"ok": True, "item": _serialize(item)}


@router.delete("/api/todos/{item_id}")
def delete_todo(item_id: int, request: Request, db: Session = Depends(get_db)):
    user = request.state.current_user
    item = _get_own(db, user.id, item_id)
    db.delete(item)
    db.commit()
    return {"ok": True}
