from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from cadybara_benchmark.api_client import CadybaraApiClient, CadybaraApiError
from cadybara_benchmark.query_images import load_api_images, query_image_api_entries
from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings
from cadybara_benchmark.ids import next_run_id
from cadybara_benchmark.json_utils import dumps_json, loads_json
from cadybara_benchmark.run_files import (
    get_run_by_id,
    list_runs as list_run_summaries,
    run_dir,
    save_run_summary,
)
from cadybara_benchmark.services.experiments import get_experiment, update_experiment_status
from cadybara_benchmark.time import utc_now


def list_runs(experiment_id: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    return list_run_summaries(experiment_id, settings)


def list_results_for_experiment(
    experiment_id: str, settings: Settings | None = None
) -> list[dict[str, Any]]:
    results = []
    for run in list_runs(experiment_id, settings):
        for query in run.get("queries", []):
            if query.get("status") != "completed":
                continue
            results.append(_query_result(run, query))
    return results


def get_result_for_run(run_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    run = get_run_by_id(run_id, settings)
    completed = [query for query in run.get("queries", []) if query.get("status") == "completed"]
    if not completed:
        return None
    scores = [query["score"] for query in completed if query.get("score") is not None]
    return {
        "run_id": run["id"],
        "queries": completed,
        "score": sum(scores) / len(scores) if scores else None,
        "metrics": {},
    }


def run_experiment(
    experiment_id: str,
    model: str | None = None,
    parameters: dict[str, Any] | None = None,
    client: CadybaraApiClient | None = None,
    settings: Settings | None = None,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
    concurrency: int = 1,
) -> dict[str, Any]:
    settings = settings or get_settings()
    experiment = get_experiment(experiment_id, settings)
    queries = experiment.get("queries", [])
    if not queries:
        raise ValueError(f"Experiment {experiment_id} has no queries to run.")
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")

    parameters = parameters or {}
    default_model = model or experiment["setup"].get("model", "default")
    base_parameters = {
        "response_mode": parameters.get(
            "response_mode", experiment["setup"].get("response_mode", settings.default_response_mode)
        ),
        "linear_deflection": parameters.get(
            "linear_deflection",
            experiment["setup"].get("linear_deflection", settings.default_linear_deflection),
        ),
        "angular_deflection": parameters.get(
            "angular_deflection",
            experiment["setup"].get("angular_deflection", settings.default_angular_deflection),
        ),
        "concurrency": concurrency,
    }
    client = client or CadybaraApiClient(settings)
    update_experiment_status(experiment_id, "running", settings)

    run_id = next_run_id(experiment_id, settings)
    started_at = utc_now()
    query_entries = [
        _initial_query_entry(experiment_id, query, default_model) for query in queries
    ]
    run_summary: dict[str, Any] = {
        "id": run_id,
        "experiment_id": experiment_id,
        "status": "running",
        "started_at": started_at,
        "finished_at": "",
        "parameters": base_parameters,
        "queries": query_entries,
        "summary": {"completed": 0, "failed": 0},
    }
    save_run_summary(run_summary, settings)

    completed = 0
    failed = 0
    summary_lock = threading.Lock()

    def execute_query(index: int) -> None:
        nonlocal completed, failed
        query = queries[index]
        query_entry = query_entries[index]

        if on_event:
            on_event(
                "started",
                {"run_id": run_id, "query_id": query["id"]},
            )

        artifact_dir = run_dir(experiment_id, run_id, settings) / query["id"]
        artifact_dir.mkdir(parents=True, exist_ok=True)
        query_entry["artifact_dir"] = _stored_path(artifact_dir)

        query_completed = 0
        query_failed = 0
        try:
            query_model = query.get("model") or default_model
            full_parameters = {**base_parameters, "model": query_model}
            stored_images = query.get("images") or []
            api_images = load_api_images(stored_images)
            if api_images:
                full_parameters = {**full_parameters, "images": api_images}
            result = client.generate(query["text"], full_parameters)
            stl_path = artifact_dir / "model.stl"
            stl_path.write_bytes(result.stl_bytes)
            response_path = artifact_dir / "response.json"
            response_path.write_text(dumps_json(result.raw_response))
            if result.generated_code:
                code_path = artifact_dir / "generated_code.py"
                code_path.write_text(result.generated_code)
            query_entry["status"] = "completed"
            query_entry["response_metadata"] = result.response_metadata
            query_entry["metrics"] = result.raw_response.get("metrics", {})
            query_completed = 1
            if on_event:
                on_event(
                    "completed",
                    {"run_id": run_id, "query_id": query["id"]},
                )
        except CadybaraApiError as exc:
            error_path = artifact_dir / "error.json"
            error_path.write_text(dumps_json(exc.payload))
            query_entry["status"] = "failed"
            query_entry["error"] = exc.payload
            query_failed = 1
            if on_event:
                on_event(
                    "failed",
                    {
                        "run_id": run_id,
                        "query_id": query["id"],
                        "error": exc.payload,
                    },
                )
        except Exception as exc:
            error = {"message": str(exc), "type": exc.__class__.__name__}
            error_path = artifact_dir / "error.json"
            error_path.write_text(dumps_json(error))
            query_entry["status"] = "failed"
            query_entry["error"] = error
            query_failed = 1
            if on_event:
                on_event(
                    "failed",
                    {
                        "run_id": run_id,
                        "query_id": query["id"],
                        "error": error,
                    },
                )

        with summary_lock:
            completed += query_completed
            failed += query_failed
            run_summary["summary"] = {"completed": completed, "failed": failed}
            save_run_summary(run_summary, settings)

    worker_count = min(concurrency, len(queries))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(execute_query, index) for index in range(len(queries))]
        for future in futures:
            future.result()

    run_summary["status"] = "completed" if failed == 0 else "completed_with_errors"
    run_summary["finished_at"] = utc_now()
    save_run_summary(run_summary, settings)

    update_experiment_status(
        experiment_id, "completed" if failed == 0 else "completed_with_errors", settings
    )
    return {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "run_ids": [run_id],
        "completed": completed,
        "failed": failed,
    }


def _initial_query_entry(
    experiment_id: str,
    query: dict[str, Any],
    default_model: str,
) -> dict[str, Any]:
    stored_images = query.get("images") or []
    return {
        "query_id": query["id"],
        "text": query["text"],
        "model": query.get("model") or default_model,
        "images": query_image_api_entries(experiment_id, query["id"], stored_images),
        "status": "running",
        "error": {},
        "artifact_dir": "",
        "response_metadata": {},
        "score": None,
        "metrics": {},
    }


def _query_result(run: dict[str, Any], query: dict[str, Any]) -> dict[str, Any]:
    artifact_dir = _resolve_path(query["artifact_dir"])
    stl_path = artifact_dir / "model.stl"
    response_path = artifact_dir / "response.json"
    raw_output = loads_json(response_path.read_text(), {}) if response_path.exists() else {}
    return {
        "id": f"{run['id']}:{query['query_id']}",
        "run_id": run["id"],
        "query_id": query["query_id"],
        "text": query.get("text", ""),
        "model": query.get("model", ""),
        "response_metadata": query.get("response_metadata", {}),
        "score": query.get("score"),
        "metrics": query.get("metrics", {}),
        "raw_output": raw_output,
        "stl_paths": [_stored_path(stl_path)] if stl_path.exists() else [],
        "artifact_paths": [_stored_path(response_path)] if response_path.exists() else [],
    }


def _resolve_path(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate


def _stored_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
