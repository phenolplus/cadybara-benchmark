from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings
from cadybara_benchmark.metrics import client_latency_ms
from cadybara_benchmark.json_utils import dumps_json
from cadybara_benchmark.services.experiments import get_experiment
from cadybara_benchmark.services.runs import list_runs
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
        completed_queries = [
            query for query in run.get("queries", []) if query.get("status") == "completed"
        ]
        if not completed_queries:
            continue

        run_dir = settings.published_dir / "runs" / run["id"]
        run_dir.mkdir(parents=True, exist_ok=True)
        published_queries = []
        for query in completed_queries:
            artifact_dir = _resolve_path(query["artifact_dir"])
            stl_path = artifact_dir / "model.stl"
            if not stl_path.exists():
                continue
            query_publish_dir = run_dir / query["query_id"]
            query_publish_dir.mkdir(parents=True, exist_ok=True)
            destination = query_publish_dir / stl_path.name
            shutil.copy2(stl_path, destination)
            published_entry: dict[str, Any] = {
                "query_id": query["query_id"],
                "sublabel": query.get("sublabel", ""),
                "text": query.get("text", ""),
                "model": query.get("model", ""),
                "stl_paths": [_stored_path(destination)],
                "score": query.get("score"),
                "metrics": query.get("metrics", {}),
                "source_artifact_paths": [_stored_path(stl_path)],
            }
            latency = client_latency_ms(query)
            if latency is not None:
                published_entry["client_latency_ms"] = latency
            published_queries.append(published_entry)

        if not published_queries:
            continue

        payload = {
            "experiment_id": experiment["id"],
            "experiment": experiment["name"],
            "run_id": run["id"],
            "published_at": utc_now(),
            "parameters": run.get("parameters", {}),
            "queries": published_queries,
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
