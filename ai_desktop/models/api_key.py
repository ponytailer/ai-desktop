"""API Key 申请记录。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .constants import (
    KEY_APPROVED,
    KEY_PENDING,
    KEY_REJECTED,
    KEY_REVOKED,
)


class ApiKey(Base):
    """API Key 申请记录。"""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicant_id: Mapped[str] = mapped_column(String(20), index=True)    # 工号
    applicant_name: Mapped[str] = mapped_column(String(80), default="")
    purpose: Mapped[str] = mapped_column(String(400), default="")        # 申请用途
    status: Mapped[str] = mapped_column(String(20), default=KEY_PENDING, index=True)

    # 分配的密钥值（approved 后填充，格式如 sk-xxxxxxxxxxxx）
    api_key_value: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # 分配时绑定的阿里云 AI Gateway 消费组（消费者）
    consumer_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    consumer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # 分配时绑定的阿里云 AI Gateway 配额规则
    quota_rule_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    quota_rule_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # ---------- 便捷属性 ----------
    @property
    def status_label(self) -> str:
        return {
            KEY_PENDING: "待审核",
            KEY_APPROVED: "已分配",
            KEY_REJECTED: "已拒绝",
            KEY_REVOKED: "已吊销",
        }.get(self.status, self.status)

    @property
    def masked_key(self) -> str:
        """脱敏后的密钥（只显示前 6 位 + ****）。"""
        if not self.api_key_value:
            return "—"
        k = self.api_key_value
        if len(k) <= 8:
            return "****"
        return k[:6] + "****" + k[-4:]
