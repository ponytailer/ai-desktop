"""TodoItem：个人工作看板待办事项。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class TodoItem(Base):
    __tablename__ = "todo_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                                 nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime,
                                                          nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
