from __future__ import annotations

from typing import Any

from cadybara_benchmark.config import Settings
from cadybara_benchmark.db import connect, dumps_json, row_to_dict, rows_to_dicts
from cadybara_benchmark.ids import next_id
from cadybara_benchmark.services.experiments import get_experiment


def add_query(
    experiment_id: str,
    text: str,
    category: str | None = None,
    metadata: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    get_experiment(experiment_id, settings)
    with connect(settings) as conn:
        query_id = next_id(conn, "queries")
        conn.execute(
            """
            INSERT INTO queries (id, experiment_id, text, category, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (query_id, experiment_id, text, category or "", dumps_json(metadata or {})),
        )
        row = conn.execute("SELECT * FROM queries WHERE id = ?", (query_id,)).fetchone()
        return row_to_dict(row, "queries")


def list_queries(experiment_id: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    get_experiment(experiment_id, settings)
    with connect(settings) as conn:
        rows = conn.execute(
            "SELECT * FROM queries WHERE experiment_id = ? ORDER BY id", (experiment_id,)
        ).fetchall()
        return rows_to_dicts(rows, "queries")


def get_query(query_id: str, settings: Settings | None = None) -> dict[str, Any]:
    with connect(settings) as conn:
        row = conn.execute("SELECT * FROM queries WHERE id = ?", (query_id,)).fetchone()
        query = row_to_dict(row, "queries")
    if query is None:
        raise ValueError(f"Query not found: {query_id}")
    return query
