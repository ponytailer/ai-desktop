"""阿里云 AI Gateway（云原生 API 网关 APIG，API 版本 2024-03-27）客户端。

按业务拆分为独立子模块：
- config    配置与环境变量（含 Mock / 生产切换开关 USE_MOCK）
- signing   V3 签名（ACS3-HMAC-SHA256，ROA 风格公共请求头）
- client    低层签名请求封装（_request）
- mock      Mock 数据与分发（仅演示用）
- consumers 消费者（Consumer）管理
- quota     配额规则（QuotaRule）CRUD 与配额用量查询

对外仍通过本包导出统一 API，调用方无需感知内部结构，例如：
    from ai_desktop.aliyun_aigw import list_consumers, create_quota_rule
"""
from __future__ import annotations

from .config import (
    ACCESS_KEY_ID,
    ACCESS_KEY_SECRET,
    ALGORITHM,
    API_VERSION,
    DEFAULT_SUBJECT_ID,
    GATEWAY_ID,
    HOST,
    QUOTA_RULE_ID,
    REGION,
    USE_MOCK,
)
from .consumers import create_consumer, delete_consumer, list_consumers
from .quota import (
    create_quota_rule,
    delete_quota_rule,
    get_quota_rule,
    get_quota_usage,
    list_quota_rules,
    update_quota_rule,
)

__all__ = [
    "API_VERSION",
    "ALGORITHM",
    "ACCESS_KEY_ID",
    "ACCESS_KEY_SECRET",
    "REGION",
    "HOST",
    "GATEWAY_ID",
    "QUOTA_RULE_ID",
    "DEFAULT_SUBJECT_ID",
    "USE_MOCK",
    "create_consumer",
    "delete_consumer",
    "list_consumers",
    "get_quota_usage",
    "create_quota_rule",
    "list_quota_rules",
    "get_quota_rule",
    "update_quota_rule",
    "delete_quota_rule",
]
