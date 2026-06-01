from __future__ import annotations

from typing import Any

from cadybara_benchmark.config import Settings, get_settings
from cadybara_benchmark.db import connect, dumps_json, row_to_dict, rows_to_dicts
from cadybara_benchmark.ids import next_id
from cadybara_benchmark.time import utc_now


def default_setup(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    return {
        "model": "default",
        "response_mode": settings.default_response_mode,
        "linear_deflection": settings.default_linear_deflection,
        "angular_deflection": settings.default_angular_deflection,
    }


def create_experiment(
    name: str,
    description: str = "",
    type: str = "query_comparison",
    setup: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    now = utc_now()
    with connect(settings) as conn:
        experiment_id = next_id(conn, "experiments")
        conn.execute(
            """
            INSERT INTO experiments (id, name, description, type, status, setup, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                name,
                description,
                type,
                "draft",
                dumps_json(setup or default_setup(settings)),
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        return row_to_dict(row, "experiments")


def list_experiments(settings: Settings | None = None) -> list[dict[str, Any]]:
    with connect(settings) as conn:
        rows = conn.execute("SELECT * FROM experiments ORDER BY created_at, id").fetchall()
        return rows_to_dicts(rows, "experiments")


def get_experiment(experiment_id: str, settings: Settings | None = None) -> dict[str, Any]:
    with connect(settings) as conn:
        row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        experiment = row_to_dict(row, "experiments")
    if experiment is None:
        raise ValueError(f"Experiment not found: {experiment_id}")
    return experiment


def update_experiment_status(
    experiment_id: str, status: str, settings: Settings | None = None
) -> dict[str, Any]:
    now = utc_now()
    with connect(settings) as conn:
        result = conn.execute(
            "UPDATE experiments SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, experiment_id),
        )
        if result.rowcount == 0:
            raise ValueError(f"Experiment not found: {experiment_id}")
        row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        return row_to_dict(row, "experiments")
