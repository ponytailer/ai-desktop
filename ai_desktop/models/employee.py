"""员工表 — 用于用户管理和角色分配。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


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
        from ..deps import ROLE_LABELS
        return " · ".join(ROLE_LABELS.get(r, r) for r in roles)

    @property
    def is_super_admin(self) -> bool:
        return "super_admin" in self.roles_list
