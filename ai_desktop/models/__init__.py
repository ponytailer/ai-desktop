"""ORM 模型包。

按业务拆分为独立子模块：
- constants 业务状态 / 枚举替代常量（作用域、审核状态、密钥状态、分类选项）
- skill     Skill 主表与版本表（Skill 市场核心领域）
- category  首页筛选用分类集合
- api_key   API Key 申请记录
- employee  员工表（用户与角色）
- feedback  用户反馈

对外通过本包统一再导出，例如：
    from ai_desktop.models import Skill, ApiKey, KEY_APPROVED, SCOPE_PUBLIC
"""
from __future__ import annotations

from .api_key import ApiKey
from .category import Category
from .constants import (
    CATEGORY_OPTIONS,
    KEY_APPROVED,
    KEY_PENDING,
    KEY_REJECTED,
    KEY_REVOKED,
    SCOPE_DEPARTMENT,
    SCOPE_PUBLIC,
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_PUBLISHED,
    STATUS_REJECTED,
    STATUS_SUPERSEDED,
)
from .employee import Employee
from .feedback import Feedback
from .skill import Skill, SkillVersion
from .todo_item import TodoItem

__all__ = [
    "SCOPE_PUBLIC",
    "SCOPE_DEPARTMENT",
    "STATUS_DRAFT",
    "STATUS_PENDING",
    "STATUS_PUBLISHED",
    "STATUS_REJECTED",
    "STATUS_SUPERSEDED",
    "CATEGORY_OPTIONS",
    "KEY_PENDING",
    "KEY_APPROVED",
    "KEY_REJECTED",
    "KEY_REVOKED",
    "Skill",
    "SkillVersion",
    "Category",
    "ApiKey",
    "Employee",
    "Feedback",
    "TodoItem",
]
