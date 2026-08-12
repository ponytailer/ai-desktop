"""当前用户 + 角色权限 + 通用依赖 + 会话管理。

使用 signed-cookie 会话：
- 登录时签发 token（HMAC-SHA256）
- 每次请求由中间件验证 cookie，设置 request.state.current_user
- 测试账密：admin / admin
"""
from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Iterable
from dataclasses import dataclass

# ---------- 角色常量 ----------

ROLE_SKILLS_ADMIN = "skills_admin"   # Skills 管理员：审核 skills
ROLE_KEY_ADMIN = "key_admin"          # 密钥管理员：审核密钥申请
ROLE_SUPER_ADMIN = "super_admin"      # 超级管理员：全部权限

ALL_ROLES = (ROLE_SKILLS_ADMIN, ROLE_KEY_ADMIN, ROLE_SUPER_ADMIN)

# 角色权限优先级（数值越大权限越高），用于「右上角只显示权限最高的角色」
ROLE_PRIORITY = {
    ROLE_SUPER_ADMIN: 3,
    ROLE_KEY_ADMIN: 2,
    ROLE_SKILLS_ADMIN: 1,
}

ROLE_LABELS = {
    ROLE_SKILLS_ADMIN: "Skills 管理员",
    ROLE_KEY_ADMIN: "密钥管理员",
    ROLE_SUPER_ADMIN: "超级管理员",
}


@dataclass(frozen=True)
class CurrentUser:
    id: str
    name: str
    avatar_label: str            # 头像里展示的几位数字
    roles: tuple[str, ...] = ()  # 角色列表

    def has_role(self, role: str) -> bool:
        """是否拥有某个角色（super_admin 隐含拥有所有权限）。"""
        return role in self.roles or ROLE_SUPER_ADMIN in self.roles

    def has_any_role(self, roles: Iterable[str]) -> bool:
        return any(self.has_role(r) for r in roles)

    @property
    def role_labels(self) -> list[str]:
        """角色中文名称列表。"""
        return [ROLE_LABELS.get(r, r) for r in self.roles]

    @property
    def highest_role(self) -> str | None:
        """权限最高的角色 key（super_admin > key_admin > skills_admin）。"""
        if not self.roles:
            return None
        return max(self.roles, key=lambda r: ROLE_PRIORITY.get(r, 0))

    @property
    def highest_role_label(self) -> str | None:
        """权限最高的角色中文名（用于右上角展示单个角色）。"""
        role = self.highest_role
        return ROLE_LABELS.get(role, role) if role else None


# ---------- 默认用户（admin 登录后映射到此）----------

CURRENT_USER = CurrentUser(
    id="48890023",
    name="Pony",
    avatar_label="48",
    roles=(ROLE_SUPER_ADMIN,),
)

# 演示用：其他用户（密钥申请记录里会用到）
# 普通测试用户（无管理角色），登录账密 test / test
TEST_USER = CurrentUser(id="10020099", name="测试用户", avatar_label="99", roles=())

DEMO_USERS = {
    "48890023": CURRENT_USER,
    "10020001": CurrentUser(id="10020001", name="张伟", avatar_label="10", roles=()),
    "10020002": CurrentUser(id="10020002", name="李娜", avatar_label="10", roles=(ROLE_KEY_ADMIN,)),
    "10020003": CurrentUser(
        id="10020003", name="王强", avatar_label="10", roles=(ROLE_SKILLS_ADMIN,)
    ),
    "10020099": TEST_USER,
}


# ---------- 会话管理 ----------

SECRET_KEY = "skillhub-secret-2026-do-not-leak"
SESSION_COOKIE_NAME = "skillhub_session"
SESSION_MAX_AGE = 30 * 24 * 3600  # 30 天（秒）

# 测试账号：username -> (password, CurrentUser)
TEST_ACCOUNTS = {
    "admin": ("admin", CURRENT_USER),
    "test": ("test", TEST_USER),
}


def create_session_token(user_id: str, max_age: int = SESSION_MAX_AGE) -> str:
    """生成签名会话 token：{user_id}:{expiry}:{hmac}。"""
    expiry = int(time.time()) + max_age
    payload = f"{user_id}:{expiry}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_session_token(token: str) -> CurrentUser | None:
    """验证会话 token，返回 CurrentUser 或 None。"""
    if not token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    user_id, expiry_str, sig = parts
    try:
        expiry = int(expiry_str)
    except ValueError:
        return None
    if time.time() > expiry:
        return None
    # 验证签名
    payload = f"{user_id}:{expiry_str}"
    expected_sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    # 查找用户
    return _lookup_user(user_id)


def _lookup_user(user_id: str) -> CurrentUser | None:
    """根据 user_id 查找 CurrentUser。"""
    if user_id in DEMO_USERS:
        return DEMO_USERS[user_id]
    return None


# ---------- 公开路径（不需要认证）----------

PUBLIC_PATHS = {
    "/login",
    "/api/auth/login",
    "/api/auth/logout",
    "/health",
}
PUBLIC_PREFIXES = (
    "/static/",
)
