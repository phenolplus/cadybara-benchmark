from __future__ import annotations

from pathlib import Path
from typing import Any

from cadybara_benchmark.config import Settings
from cadybara_benchmark.experiment_files import save_experiment
from cadybara_benchmark.ids import next_query_id
from cadybara_benchmark.query_images import (
    query_image_api_entries,
    save_query_image_files,
    save_query_images,
)
from cadybara_benchmark.services.experiments import get_experiment
from cadybara_benchmark.time import utc_now


def add_query(
    experiment_id: str,
    text: str,
    category: str | None = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
    images: list[dict[str, Any]] | None = None,
    image_paths: list[Path] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    text = text.strip()
    if not text and not images and not image_paths:
        raise ValueError("Query requires text or at least one image.")

    experiment = get_experiment(experiment_id, settings)
    query_id = next_query_id(experiment)
    stored_images: list[dict[str, str]] = []
    if images:
        stored_images = save_query_images(experiment_id, query_id, images, settings)
    elif image_paths:
        stored_images = save_query_image_files(experiment_id, query_id, image_paths, settings)

    query = {
        "id": query_id,
        "experiment_id": experiment_id,
        "text": text,
        "model": model or "",
        "category": category or "",
        "metadata": metadata or {},
        "images": stored_images,
    }
    experiment.setdefault("queries", []).append(_stored_query(query))
    experiment["updated_at"] = utc_now()
    save_experiment(experiment, settings)
    return _with_experiment_id(query, experiment_id)


def list_queries(experiment_id: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    experiment = get_experiment(experiment_id, settings)
    return [
        _with_experiment_id(query, experiment_id) for query in experiment.get("queries", [])
    ]


def get_query(
    query_id: str,
    settings: Settings | None = None,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    from cadybara_benchmark.services.experiments import list_experiments

    experiments = (
        [get_experiment(experiment_id, settings)] if experiment_id else list_experiments(settings)
    )
    for experiment in experiments:
        for query in experiment.get("queries", []):
            if query["id"] == query_id:
                return _with_experiment_id(query, experiment["id"])
    raise ValueError(f"Query not found: {query_id}")


def _stored_query(query: dict[str, Any]) -> dict[str, Any]:
    stored = {
        "id": query["id"],
        "text": query["text"],
        "model": query.get("model", ""),
        "category": query.get("category", ""),
        "metadata": query.get("metadata", {}),
    }
    images = query.get("images") or []
    if images:
        stored["images"] = images
    return stored


def _with_experiment_id(query: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    images = query.get("images") or []
    return {
        "id": query["id"],
        "experiment_id": experiment_id,
        "text": query.get("text", ""),
        "model": query.get("model", ""),
        "category": query.get("category", ""),
        "metadata": query.get("metadata", {}),
        "images": query_image_api_entries(experiment_id, query["id"], images),
    }
