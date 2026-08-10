"""用户反馈 — 右上角「反馈」表单提交的内容。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Feedback(Base):
    """用户反馈 — 右上角「反馈」表单提交的内容。"""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, default="")          # 反馈正文
    employee_id: Mapped[str] = mapped_column(String(20), default="")  # 提交人工号
    employee_name: Mapped[str] = mapped_column(String(80), default="")  # 提交人姓名
    is_read: Mapped[bool] = mapped_column(default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def preview(self, length: int = 60) -> str:
        """列表预览：超长截断。"""
        text = self.content or ""
        return text if len(text) <= length else text[:length] + "…"

    @property
    def created_label(self) -> str:
        return self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else ""

    @property
    def is_unread(self) -> bool:
        return not self.is_read
