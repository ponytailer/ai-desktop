"""Mock 数据分支（仅演示用，生产删除/注释本段即可）。

与真实接口返回结构保持一致，用于驱动图表与列表展示。
"""
from __future__ import annotations

import re
import uuid
from typing import Any

# 内存态配额规则（仅 mock 模式使用，用于模拟 CRUD 的持久效果）
_MOCK_QUOTA_RULES: list[dict[str, Any]] = [
    {
        "ruleId": "qr-mock-001",
        "ruleName": "default-token",
        "quotaDimension": "token",
        "quotaLimit": 1000,
        "ruleStatus": "enabled",
        "periodType": "day",
        "timezone": "UTC+8",
        "windowAlignment": "calendar",
        "consumerIds": ["cs-mock-001"],
    },
    {
        "ruleId": "qr-mock-002",
        "ruleName": "team-credit-weekly",
        "quotaDimension": "credit",
        "quotaLimit": 5000,
        "ruleStatus": "enabled",
        "periodType": "week",
        "timezone": "UTC+8",
        "windowAlignment": "calendar",
        "consumerIds": [],
    },
]


def _mock_quota_usage() -> dict[str, Any]:
    """与 GetGatewayQuotaRuleSubjectUsage 真实返回结构一致的 mock。"""
    items = [
        {"model": "qwen-plus", "inputAmount": 120, "outputAmount": 80, "cachedAmount": 10,
         "usedAmount": 210, "startTime": "2026-08-05 13:16:31"},
        {"model": "qwen-max", "inputAmount": 90, "outputAmount": 60, "cachedAmount": 8,
         "usedAmount": 158, "startTime": "2026-08-06 09:01:12"},
        {"model": "deepseek-v3", "inputAmount": 70, "outputAmount": 30, "cachedAmount": 10,
         "usedAmount": 110, "startTime": "2026-08-07 18:22:43"},
        {"model": "glm-4", "inputAmount": 30, "outputAmount": 10, "cachedAmount": 5,
         "usedAmount": 45, "startTime": "2026-08-08 11:05:09"},
    ]
    totals = {
        k: sum(i.get(k, 0) for i in items)
        for k in ("inputAmount", "outputAmount", "cachedAmount", "usedAmount")
    }
    return {
        "requestId": "mock-" + uuid.uuid4().hex[:12],
        "code": "200",
        "message": "success",
        "data": {
            "usedAmount": totals["usedAmount"],
            "totalQuota": 1000,
            "overLimit": totals["usedAmount"] > 1000,
            "inputAmount": totals["inputAmount"],
            "outputAmount": totals["outputAmount"],
            "cachedAmount": totals["cachedAmount"],
            "details": {
                "totalSize": len(items),
                "pageNumber": 1,
                "pageSize": 10,
                "items": items,
            },
        },
    }


def _mock_dispatch(
    method: str,
    path: str,
    query: dict[str, Any] | None,
    body: dict[str, Any] | None,
) -> dict[str, Any]:
    if method == "POST" and path == "/v1/consumers":
        name = (body or {}).get("name", "mock-consumer")
        return {
            "requestId": "mock-" + uuid.uuid4().hex[:12],
            "code": "Ok",
            "message": "success",
            "data": {"consumerId": "cs-mock-" + uuid.uuid4().hex[:8]},
            "_mock_name": name,
        }
    if method == "DELETE" and path.startswith("/v1/consumers/"):
        return {
            "requestId": "mock-" + uuid.uuid4().hex[:12],
            "code": "Ok",
            "message": "success",
        }
    if method == "GET" and path == "/v1/consumers":
        return {
            "requestId": "mock-" + uuid.uuid4().hex[:12],
            "code": "Ok",
            "message": "success",
            "data": {
                "items": [
                    {
                        "consumerId": "cs-mock-001",
                        "name": "demo-consumer",
                        "description": "演示消费者",
                        "gatewayType": "AI",
                        "enable": True,
                    },
                    {
                        "consumerId": "cs-mock-002",
                        "name": "team-alpha",
                        "description": "Alpha 团队网关消费者",
                        "gatewayType": "AI",
                        "enable": True,
                    },
                ],
                "total": 2,
            },
        }
    # 配额规则 CRUD（mock）
    _qlist = re.match(r"/v1/gateways/[^/]+/quota-rules$", path)
    _qsingle = re.match(r"/v1/gateways/[^/]+/quota-rules/([^/]+)$", path)
    if _qlist and method == "GET":
        return {
            "requestId": "mock", "code": "Ok", "message": "success",
            "data": {"items": list(_MOCK_QUOTA_RULES), "totalSize": len(_MOCK_QUOTA_RULES)},
        }
    if _qlist and method == "POST":
        b = body or {}
        rid = "qr-mock-" + uuid.uuid4().hex[:8]
        rule = {
            "ruleId": rid,
            "ruleName": (b.get("ruleName") or "rule"),
            "quotaDimension": b.get("quotaDimension", "token"),
            "quotaLimit": int(b.get("quotaLimit") or 0),
            "ruleStatus": "enabled",
            "periodType": b.get("periodType", "day"),
            "timezone": b.get("timezone", "UTC+8"),
            "windowAlignment": b.get("windowAlignment", "calendar"),
            "consumerIds": list(b.get("consumerIds") or []),
        }
        _MOCK_QUOTA_RULES.append(rule)
        return {"requestId": "mock", "code": "Ok", "message": "success", "data": {"ruleId": rid}}
    if _qsingle:
        rid = _qsingle.group(1)
        if method == "GET":
            rule = next((r for r in _MOCK_QUOTA_RULES if r["ruleId"] == rid), None)
            return {"requestId": "mock", "code": "Ok", "message": "success", "data": rule or {}}
        if method == "PUT":
            rule = next((r for r in _MOCK_QUOTA_RULES if r["ruleId"] == rid), None)
            if rule:
                b = body or {}
                if "ruleName" in b:
                    rule["ruleName"] = b["ruleName"]
                if "quotaLimit" in b:
                    rule["quotaLimit"] = int(b["quotaLimit"])
                if b.get("addIds"):
                    rule.setdefault("consumerIds", [])
                    for cid in b["addIds"]:
                        if cid not in rule["consumerIds"]:
                            rule["consumerIds"].append(cid)
                if b.get("removeIds"):
                    rule["consumerIds"] = [
                        c for c in rule.get("consumerIds", []) if c not in b["removeIds"]
                    ]
            return {"requestId": "mock", "code": "Ok", "message": "success", "data": rule or {}}
        if method == "DELETE":
            _MOCK_QUOTA_RULES[:] = [r for r in _MOCK_QUOTA_RULES if r["ruleId"] != rid]
            return {"requestId": "mock", "code": "Ok", "message": "success"}
    if method == "GET" and "/usage" in path:
        return _mock_quota_usage()
    return {"requestId": "mock", "code": "Ok", "message": "success", "data": {}}
