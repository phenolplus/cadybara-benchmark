from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings
from cadybara_benchmark.db import dumps_json
from cadybara_benchmark.services.experiments import get_experiment
from cadybara_benchmark.services.queries import get_query
from cadybara_benchmark.services.runs import get_result_for_run, list_runs
from cadybara_benchmark.time import utc_now


def publish_experiment(
    experiment_id: str,
    run_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    experiment = get_experiment(experiment_id, settings)
    runs = list_runs(experiment_id, settings)
    if run_id:
        runs = [run for run in runs if run["id"] == run_id]
    runs = [run for run in runs if run["status"] == "completed"]

    published = []
    for run in runs:
        result = get_result_for_run(run["id"], settings)
        if result is None:
            continue
        query = get_query(run["query_id"], settings)
        run_dir = settings.published_dir / "runs" / run["id"]
        run_dir.mkdir(parents=True, exist_ok=True)
        copied_stl_paths = []
        for raw_path in result["stl_paths"]:
            source = _resolve_path(raw_path)
            destination = run_dir / source.name
            shutil.copy2(source, destination)
            copied_stl_paths.append(_stored_path(destination))

        payload = {
            "experiment_id": experiment["id"],
            "experiment": experiment["name"],
            "run_id": run["id"],
            "published_at": utc_now(),
            "query": {
                "id": query["id"],
                "text": query["text"],
                "category": query["category"],
                "metadata": query["metadata"],
            },
            "model": run["model"],
            "parameters": run["parameters"],
            "response_metadata": result["response_metadata"],
            "stl_paths": copied_stl_paths,
            "score": result["score"],
            "metrics": result["metrics"],
            "source_artifact_paths": result["stl_paths"],
        }
        json_path = settings.published_dir / "runs" / f"{run['id']}.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(dumps_json(payload))
        published.append(_stored_path(json_path))

    return {"experiment_id": experiment_id, "published": published, "count": len(published)}


def _resolve_path(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    if not candidate.exists():
        raise FileNotFoundError(f"Artifact not found: {path}")
    return candidate


def _stored_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
