"""ORM models。

设计原则：

- 一个 Skill 是一条逻辑资产，可以有多个 Version。
- 每个 Version 都有自己的审核状态（草稿 / 待审核 / 已发布 / 已拒绝）。
- "已上架"指至少有一个 Version.status == 'published'，且对外展示这个版本。
- tags、author_team 等存 JSON 字符串，避免关联表的复杂度。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# ---------- 常量（业务状态 / 枚举替代品）----------

SCOPE_PUBLIC = "public"           # 公开  — 企业内所有员工可见
SCOPE_DEPARTMENT = "department"   # 部门内可见 — 仅数字化工作台员工可见

STATUS_DRAFT = "draft"             # 草稿
STATUS_PENDING = "pending"         # 待审核
STATUS_PUBLISHED = "published"     # 已发布
STATUS_REJECTED = "rejected"       # 已拒绝
STATUS_SUPERSEDED = "superseded"   # 已被新版本替代（同一个 skill 的老 published 版本）

CATEGORY_OPTIONS = [
    "研发工具",
    "代码质量",
    "数据与分析",
    "会议与协作",
    "运营增长",
    "安全合规",
    "业务运营",
    "客服与支持",
]


# ---------- 密钥管理状态常量 ----------

KEY_PENDING = "pending"       # 待审核
KEY_APPROVED = "approved"     # 已分配
KEY_REJECTED = "rejected"     # 已拒绝
KEY_REVOKED = "revoked"       # 已吊销


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


class Category(Base):
    """首页筛选下拉「全部分类」用的二级分类集合，名字自取即可。"""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


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


class Employee(Base):
    """员工表 — 用于用户管理和角色分配。"""

    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # 工号
    name: Mapped[str] = mapped_column(String(80), default="")
    department: Mapped[str] = mapped_column(String(80), default="")
    _roles: Mapped[str] = mapped_column("roles", String(200), default="[]")
    is_test_data: Mapped[bool] = mapped_column(default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # ---------- 便捷属性 ----------
    @property
    def roles_list(self) -> list[str]:
        try:
            return json.loads(self._roles or "[]")
        except json.JSONDecodeError:
            return []

    def set_roles(self, items: list[str]) -> None:
        self._roles = json.dumps(items or [], ensure_ascii=False)

    @property
    def role_label(self) -> str:
        roles = self.roles_list
        if not roles:
            return "普通员工"
        from .deps import ROLE_LABELS
        return " · ".join(ROLE_LABELS.get(r, r) for r in roles)

    @property
    def is_super_admin(self) -> bool:
        return "super_admin" in self.roles_list


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
