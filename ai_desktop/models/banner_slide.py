"""首页轮播自定义幻灯片（管理员运营内容，如公司通知）。

默认「工作看板」slide 不在本表，由首页固定渲染；本表仅存放管理员
可增删的自定义幻灯片。is_active=False 的幻灯片不在首页展示。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class BannerSlide(Base):
    """首页轮播的自定义幻灯片。"""

    __tablename__ = "banner_slide"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120), default="")
    content: Mapped[str] = mapped_column(Text, default="")

    # 可选跳转链接（仅允许 http/https，服务端已校验）
    link: Mapped[str] = mapped_column(String(300), default="")
    # 链接按钮文字（link 为空时忽略）
    link_text: Mapped[str] = mapped_column(String(60), default="")

    # 主题色预设：orange / green / blue / purple（决定幻灯片渐变）
    accent: Mapped[str] = mapped_column(String(20), default="orange")

    # 是否在前台展示
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # 排序，越小越靠前
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # 有效期（可选）：start_at / end_at 都为空 = 长期展示；
    # 否则仅在 [start_at, end_at] 区间内（且 is_active）才在前台出现。
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
