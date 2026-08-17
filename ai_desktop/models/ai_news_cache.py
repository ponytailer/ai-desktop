"""首页 AI 资讯按日缓存（服务端缓存，避免每位访客重复抓取）。

一条记录代表「某自然日」的 AI 资讯 Top5，JSON 存于 payload。
命中缓存直接返回，TTL 过期才触发一次后台刷新。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class AiNewsCache(Base):
    """按自然日缓存的 AI 资讯（top5）。"""

    __tablename__ = "ai_news_cache"
    __table_args__ = (
        UniqueConstraint("news_date", name="uq_ai_news_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 自然日 YYYY-MM-DD，每日唯一
    news_date: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    # JSON 列表：[{"title","url","summary","source"}]
    payload: Mapped[str] = mapped_column(Text, default="[]")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
