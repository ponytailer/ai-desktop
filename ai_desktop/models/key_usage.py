"""API Key 月度用量快照（管理后台配额分析用）。

一条记录代表「某用户在某自然月」的额度分配与实际消耗，
便于按月份查看每个已分配密钥用户的使用情况，进而调整配额。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class KeyUsage(Base):
    """API Key 月度用量快照。"""

    __tablename__ = "key_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "month", name="uq_key_usage_user_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(20), index=True)        # 工号
    user_name: Mapped[str] = mapped_column(String(80), default="")
    department: Mapped[str] = mapped_column(String(120), default="")

    # 自然月，格式 YYYY-MM
    month: Mapped[str] = mapped_column(String(7), index=True)

    # 本月分配的额度（token / credit 等，单位与配额规则一致）
    allocated: Mapped[int] = mapped_column(Integer, default=0)
    # 本月已使用量
    used: Mapped[int] = mapped_column(Integer, default=0)

    # 是否为演示种子数据（真实网关接入后可通过同步覆盖）
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @property
    def rate(self) -> float:
        """使用率（0~1），分配为 0 时视作 0。"""
        if self.allocated <= 0:
            return 0.0
        return min(self.used / self.allocated, 1.0)

    @property
    def rate_pct(self) -> int:
        return int(round(self.rate * 100))

    @property
    def over_threshold(self) -> bool:
        """是否达到高水位（>=90%），提示需要扩容。"""
        return self.rate >= 0.9

    @property
    def low_usage(self) -> bool:
        """是否长期低使用（<=20%），提示可缩容或关注。"""
        return self.allocated > 0 and self.rate <= 0.2
