from __future__ import annotations

from typing import Any


def client_latency_ms(query: dict[str, Any]) -> int | None:
    meta = query.get("response_metadata") or {}
    if isinstance(meta.get("latency_ms"), int):
        return meta["latency_ms"]
    error = query.get("error") or {}
    if isinstance(error.get("latency_ms"), int):
        return error["latency_ms"]
    return None


def average_client_latency_ms(queries: list[dict[str, Any]]) -> int | None:
    values = [latency for query in queries if (latency := client_latency_ms(query)) is not None]
    if not values:
        return None
    return int(sum(values) / len(values))
