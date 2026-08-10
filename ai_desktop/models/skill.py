"""Skill 主表与版本表（Skill 市场核心领域模型）。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .constants import (
    SCOPE_PUBLIC,
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_PUBLISHED,
    STATUS_REJECTED,
    STATUS_SUPERSEDED,
)


class Skill(Base):
    """Skill 主表。聚合所有版本，并保存「市场卡片」展示字段。"""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    icon: Mapped[str] = mapped_column(String(8), default="📦")  # emoji 占位
    accent_color: Mapped[str] = mapped_column(String(16), default="#5B6CFF")  # 卡片左色条
    short_description: Mapped[str] = mapped_column(String(400), default="")
    category: Mapped[str] = mapped_column(String(40), default="研发工具")
    owner_name: Mapped[str] = mapped_column(String(80), default="贡献者")
    owner_team: Mapped[str] = mapped_column(String(80), default="未指定团队")
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    is_featured: Mapped[bool] = mapped_column(default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    versions: Mapped[list[SkillVersion]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillVersion.created_at.desc()",
    )

    # ---------- 便捷属性 ----------
    @property
    def published_version(self) -> SkillVersion | None:
        for v in self.versions:
            if v.status == STATUS_PUBLISHED:
                return v
        return None

    @property
    def tags(self) -> list[str]:
        v = self.published_version
        return v.tags_list if v else []

    @property
    def version_label(self) -> str:
        v = self.published_version
        return v.version if v else "0.0.0"

    @property
    def display_title_color(self) -> str:
        """首页卡片标题颜色（SQL Insight=蓝紫 / Meeting Brief=青 等）。"""
        return self.accent_color


class SkillVersion(Base):
    """Skill 的具体版本，承载审核流程。"""

    __tablename__ = "skill_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(40), default="1.0.0")
    summary: Mapped[str] = mapped_column(String(400), default="")  # 一句话简介
    # 详细说明（输入 / 流程 / 输出 / 适用边界）
    detail: Mapped[str] = mapped_column(Text, default="")
    changelog: Mapped[str] = mapped_column(Text, default="")  # 本版本的版本说明

    scope: Mapped[str] = mapped_column(String(20), default=SCOPE_PUBLIC)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING)

    # tags 用 JSON 字符串存，简化
    _tags: Mapped[str] = mapped_column("tags", String(800), default="[]")

    # 附件 zip 本地路径（相对于附件根目录）
    attachment_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    attachment_size: Mapped[int] = mapped_column(Integer, default=0)  # 字节

    submitted_by: Mapped[str] = mapped_column(String(80), default="")
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    featured_badge: Mapped[bool] = mapped_column(default=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    skill: Mapped[Skill] = relationship(back_populates="versions")

    # ---------- 便捷属性 ----------
    @property
    def tags_list(self) -> list[str]:
        try:
            data = json.loads(self._tags or "[]")
            return [str(x) for x in data]
        except json.JSONDecodeError:
            return []

    def set_tags(self, items: list[str]) -> None:
        self._tags = json.dumps(items or [], ensure_ascii=False)

    @property
    def scope_label(self) -> str:
        return "公开" if self.scope == SCOPE_PUBLIC else "部门内可见"

    @property
    def status_label(self) -> str:
        return {
            STATUS_DRAFT: "草稿",
            STATUS_PENDING: "待审核",
            STATUS_PUBLISHED: "已通过",
            STATUS_REJECTED: "已拒绝",
            STATUS_SUPERSEDED: "已替代",
        }.get(self.status, self.status)

    @property
    def size_human(self) -> str:
        b = self.attachment_size
        if b <= 0:
            return "—"
        if b < 1024:
            return f"{b} B"
        if b < 1024 * 1024:
            return f"{b / 1024:.0f} KB"
        return f"{b / 1024 / 1024:.1f} MB"
