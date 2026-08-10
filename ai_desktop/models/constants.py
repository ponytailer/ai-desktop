"""业务状态 / 枚举替代常量。

集中放置 Skill、ApiKey 等共享的状态枚举与分类选项，避免散落在各模型类里。
"""
from __future__ import annotations

# ---------- Skill 作用域 ----------
SCOPE_PUBLIC = "public"           # 公开  — 企业内所有员工可见
SCOPE_DEPARTMENT = "department"   # 部门内可见 — 仅数字化工作台员工可见

# ---------- Skill 版本审核状态 ----------
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

# ---------- 密钥管理状态 ----------
KEY_PENDING = "pending"       # 待审核
KEY_APPROVED = "approved"     # 已分配
KEY_REJECTED = "rejected"     # 已拒绝
KEY_REVOKED = "revoked"       # 已吊销
