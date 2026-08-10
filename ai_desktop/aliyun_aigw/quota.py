"""配额规则（QuotaRule）CRUD 与配额用量查询业务方法。

已对接接口：
- GetGatewayQuotaRuleSubjectUsage
      GET /v1/gateways/{gatewayId}/quota-rules/{ruleId}/subjects/{subjectId}/usage
- AddGatewayQuotaRule               POST /v1/gateways/{gatewayId}/quota-rules
- ListGatewayQuotaRules             GET  /v1/gateways/{gatewayId}/quota-rules
- GetGatewayQuotaRule               GET  /v1/gateways/{gatewayId}/quota-rules/{ruleId}
- UpdateGatewayQuotaRule            PUT  /v1/gateways/{gatewayId}/quota-rules/{ruleId}
- DeleteGatewayQuotaRule            DELETE /v1/gateways/{gatewayId}/quota-rules/{ruleId}
"""
from __future__ import annotations

from typing import Any

from .client import _request
from .config import DEFAULT_SUBJECT_ID, GATEWAY_ID, QUOTA_RULE_ID, USE_MOCK
from .mock import _mock_quota_usage


def get_quota_usage(
    subject_id: str | None = None,
    *,
    page_number: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """获取某消费者在配额规则下的积分用量。

    subject_id 缺省时回退到环境变量 ALIYUN_APIG_SUBJECT_ID。
    gatewayId / ruleId 来自环境变量 ALIYUN_APIG_GATEWAY_ID / ALIYUN_APIG_QUOTA_RULE_ID。
    """
    subject_id = subject_id or DEFAULT_SUBJECT_ID
    if USE_MOCK:
        # Mock 模式无需真实网关/主体配置
        return _mock_quota_usage()

    if not subject_id:
        raise ValueError("缺少 subject_id（传参或配置 ALIYUN_APIG_SUBJECT_ID）")
    if not (GATEWAY_ID and QUOTA_RULE_ID):
        raise ValueError(
            "缺少网关/配额规则配置：ALIYUN_APIG_GATEWAY_ID / ALIYUN_APIG_QUOTA_RULE_ID"
        )

    path = (
        f"/v1/gateways/{GATEWAY_ID}/quota-rules/{QUOTA_RULE_ID}"
        f"/subjects/{subject_id}/usage"
    )
    query = {"pageNumber": page_number, "pageSize": min(page_size, 10)}
    return _request("GET", path, action="GetGatewayQuotaRuleSubjectUsage", query=query)


def create_quota_rule(
    rule_name: str,
    quota_dimension: str,
    quota_limit: int,
    *,
    period_type: str = "day",
    window_alignment: str = "calendar",
    timezone: str = "UTC+8",
    consumer_ids: list[str] | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """新增消费者配额规则（AddGatewayQuotaRule）。"""
    if not USE_MOCK and not GATEWAY_ID:
        raise ValueError("缺少网关配置：ALIYUN_APIG_GATEWAY_ID")
    body: dict[str, Any] = {
        "ruleName": rule_name,
        "quotaDimension": quota_dimension,
        "quotaLimit": int(quota_limit),
        "periodType": period_type,
        "windowAlignment": window_alignment,
        "timezone": timezone,
    }
    if consumer_ids:
        body["consumerIds"] = consumer_ids
    if dry_run:
        body["dryRun"] = True
    if overwrite:
        body["overwrite"] = True
    return _request(
        "POST",
        f"/v1/gateways/{GATEWAY_ID or 'gw-mock'}/quota-rules",
        action="AddGatewayQuotaRule",
        body=body,
    )


def list_quota_rules(
    keyword: str | None = None,
    page_number: int = 1,
    page_size: int = 20,
) -> list[dict[str, Any]]:
    """列出配额规则（ListGatewayQuotaRules）。"""
    if not USE_MOCK and not GATEWAY_ID:
        raise ValueError("缺少网关配置：ALIYUN_APIG_GATEWAY_ID")
    query: dict[str, Any] = {"pageNumber": page_number, "pageSize": page_size}
    if keyword:
        query["keyword"] = keyword
    resp = _request(
        "GET",
        f"/v1/gateways/{GATEWAY_ID or 'gw-mock'}/quota-rules",
        action="ListGatewayQuotaRules",
        query=query,
    )
    data = resp.get("data") or {}
    items = data.get("items") if isinstance(data, dict) else data
    return items or []


def get_quota_rule(rule_id: str) -> dict[str, Any]:
    """获取单条配额规则（GetGatewayQuotaRule）。"""
    if not USE_MOCK and not GATEWAY_ID:
        raise ValueError("缺少网关配置：ALIYUN_APIG_GATEWAY_ID")
    resp = _request(
        "GET",
        f"/v1/gateways/{GATEWAY_ID or 'gw-mock'}/quota-rules/{rule_id}",
        action="GetGatewayQuotaRule",
    )
    return resp.get("data") or resp


def update_quota_rule(
    rule_id: str,
    *,
    rule_name: str | None = None,
    quota_limit: int | None = None,
    add_ids: list[str] | None = None,
    remove_ids: list[str] | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """编辑配额规则（UpdateGatewayQuotaRule）。"""
    if not USE_MOCK and not GATEWAY_ID:
        raise ValueError("缺少网关配置：ALIYUN_APIG_GATEWAY_ID")
    body: dict[str, Any] = {}
    if rule_name is not None:
        body["ruleName"] = rule_name
    if quota_limit is not None:
        body["quotaLimit"] = int(quota_limit)
    if add_ids:
        body["addIds"] = add_ids
    if remove_ids:
        body["removeIds"] = remove_ids
    if dry_run:
        body["dryRun"] = True
    if overwrite:
        body["overwrite"] = True
    return _request(
        "PUT",
        f"/v1/gateways/{GATEWAY_ID or 'gw-mock'}/quota-rules/{rule_id}",
        action="UpdateGatewayQuotaRule",
        body=body,
    )


def delete_quota_rule(rule_id: str) -> dict[str, Any]:
    """删除配额规则（DeleteGatewayQuotaRule）。"""
    if not USE_MOCK and not GATEWAY_ID:
        raise ValueError("缺少网关配置：ALIYUN_APIG_GATEWAY_ID")
    return _request(
        "DELETE",
        f"/v1/gateways/{GATEWAY_ID or 'gw-mock'}/quota-rules/{rule_id}",
        action="DeleteGatewayQuotaRule",
    )
