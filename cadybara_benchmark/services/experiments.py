from __future__ import annotations

from typing import Any

from cadybara_benchmark.config import Settings, get_settings
from cadybara_benchmark.experiment_files import (
    load_experiment,
    load_experiments,
    save_experiment,
)
from cadybara_benchmark.ids import next_experiment_id
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
    experiment = {
        "id": next_experiment_id(settings),
        "name": name,
        "description": description,
        "type": type,
        "status": "draft",
        "setup": setup or default_setup(settings),
        "created_at": now,
        "updated_at": now,
        "queries": [],
    }
    save_experiment(experiment, settings)
    return experiment


def list_experiments(settings: Settings | None = None) -> list[dict[str, Any]]:
    experiments = load_experiments(settings)
    return sorted(experiments, key=lambda experiment: (experiment.get("created_at", ""), experiment["id"]))


def get_experiment(experiment_id: str, settings: Settings | None = None) -> dict[str, Any]:
    return load_experiment(experiment_id, settings)


def update_experiment_status(
    experiment_id: str, status: str, settings: Settings | None = None
) -> dict[str, Any]:
    now = utc_now()
    experiment = get_experiment(experiment_id, settings)
    experiment["status"] = status
    experiment["updated_at"] = now
    save_experiment(experiment, settings)
    return experiment
