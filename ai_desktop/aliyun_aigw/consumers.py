"""消费者（Consumer）管理业务方法。

已对接接口：
- CreateConsumer   POST   /v1/consumers
- DeleteConsumer   DELETE /v1/consumers/{consumerId}
- ListConsumers    GET    /v1/consumers
"""
from __future__ import annotations

from typing import Any

from .client import _request


def create_consumer(
    name: str,
    *,
    description: str = "",
    enable: bool = True,
    gateway_type: str = "AI",
) -> dict[str, Any]:
    """创建消费者。gateway_type=AI 表示 AI 网关消费者。"""
    body = {
        "name": name,
        "description": description,
        "enable": enable,
        "gatewayType": gateway_type,
    }
    return _request("POST", "/v1/consumers", action="CreateConsumer", body=body)


def delete_consumer(consumer_id: str) -> dict[str, Any]:
    """删除消费者。"""
    return _request(
        "DELETE",
        f"/v1/consumers/{consumer_id}",
        action="DeleteConsumer",
    )


def list_consumers() -> list[dict[str, Any]]:
    """列出消费者（用于管理页），返回 data 列表。"""
    resp = _request("GET", "/v1/consumers", action="ListConsumers")
    # ListConsumers 返回 {code, data: {items: [...]}, ...}
    data = resp.get("data") or {}
    items = data.get("items") if isinstance(data, dict) else data
    return items or []
