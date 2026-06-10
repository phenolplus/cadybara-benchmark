from __future__ import annotations

from typing import Any

_FINISHED_QUERY_STATUSES = frozenset({"completed", "failed", "cancelled"})
_IN_PROGRESS_QUERY_STATUSES = frozenset({"pending", "running"})


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


def total_client_latency_ms(queries: list[dict[str, Any]]) -> int | None:
    values = [latency for query in queries if (latency := client_latency_ms(query)) is not None]
    if not values:
        return None
    return sum(values)


def run_eta_ms(queries: list[dict[str, Any]]) -> int | None:
    finished_latencies = [
        latency
        for query in queries
        if query.get("status") in _FINISHED_QUERY_STATUSES
        and (latency := client_latency_ms(query)) is not None
    ]
    remaining = len(
        [query for query in queries if query.get("status") in _IN_PROGRESS_QUERY_STATUSES]
    )
    if not finished_latencies or remaining == 0:
        return None
    average = sum(finished_latencies) / len(finished_latencies)
    return int(average * remaining)
