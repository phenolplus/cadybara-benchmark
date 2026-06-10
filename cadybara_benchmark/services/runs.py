from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cadybara_benchmark.api_client import CadybaraApiClient, CadybaraApiError
from cadybara_benchmark.geometry import write_generate_artifacts
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


@dataclass
class _ActiveRun:
    experiment_id: str
    cancel_event: threading.Event
    lock: threading.Lock
    run_summary: dict[str, Any]


_active_runs: dict[str, _ActiveRun] = {}
_active_runs_lock = threading.Lock()


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


def resume_run(
    experiment_id: str,
    run_id: str,
    client: CadybaraApiClient | None = None,
    settings: Settings | None = None,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
    concurrency: int | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if _get_active_run(run_id) is not None:
        raise ValueError(f"Run {run_id} is already running.")

    run_summary = get_run_by_id(run_id, settings)
    if run_summary.get("experiment_id") != experiment_id:
        raise ValueError(f"Run not found: {run_id}")
    if run_summary["status"] != "stopped":
        raise ValueError(f"Run {run_id} is not stopped.")

    cancelled_indices = [
        index
        for index, query_entry in enumerate(run_summary.get("queries", []))
        if query_entry.get("status") == "cancelled"
    ]
    if not cancelled_indices:
        raise ValueError(f"Run {run_id} has no cancelled queries to resume.")

    experiment = get_experiment(experiment_id, settings)
    experiment_queries = {query["id"]: query for query in experiment.get("queries", [])}
    base_parameters = dict(run_summary.get("parameters") or {})
    output_format = str(base_parameters.get("output_format", "stl"))
    if output_format not in {"stl", "step"}:
        raise ValueError("output_format must be 'stl' or 'step'")
    worker_concurrency = concurrency if concurrency is not None else int(base_parameters.get("concurrency", 1))
    if worker_concurrency < 1:
        raise ValueError("concurrency must be at least 1")

    default_model = experiment["setup"].get("model", "default")
    client = client or CadybaraApiClient(settings)
    update_experiment_status(experiment_id, "running", settings)

    run_summary["status"] = "running"
    run_summary["finished_at"] = ""
    save_run_summary(run_summary, settings)

    cancel_event = threading.Event()
    summary_lock = threading.Lock()
    active_run = _ActiveRun(
        experiment_id=experiment_id,
        cancel_event=cancel_event,
        lock=summary_lock,
        run_summary=run_summary,
    )
    _register_active_run(run_id, active_run)

    if on_event:
        on_event(
            "run_started",
            {"run_id": run_id, "experiment_id": experiment_id, "resumed": True},
        )

    work_items: list[tuple[int, dict[str, Any]]] = []
    for index in cancelled_indices:
        query_entry = run_summary["queries"][index]
        experiment_query = experiment_queries.get(query_entry["query_id"])
        if experiment_query is None:
            raise ValueError(f"Query not found in experiment: {query_entry['query_id']}")
        work_items.append((index, experiment_query))

    try:
        stopped = _run_query_work(
            experiment_id=experiment_id,
            run_id=run_id,
            run_summary=run_summary,
            work_items=work_items,
            base_parameters=base_parameters,
            default_model=default_model,
            output_format=output_format,
            client=client,
            settings=settings,
            cancel_event=cancel_event,
            summary_lock=summary_lock,
            on_event=on_event,
            concurrency=worker_concurrency,
        )
    finally:
        _unregister_active_run(run_id)

    summary = run_summary.get("summary", {})
    return {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "run_ids": [run_id],
        "completed": summary.get("completed", 0),
        "failed": summary.get("failed", 0),
        "stopped": stopped,
        "resumed": True,
    }


def stop_run(
    experiment_id: str,
    run_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    active = _get_active_run(run_id)
    if active is not None:
        if active.experiment_id != experiment_id:
            raise ValueError(f"Run not found: {run_id}")
        active.cancel_event.set()
        with active.lock:
            if active.run_summary["status"] != "running":
                raise ValueError(f"Run {run_id} is not running.")
            _mark_run_stopped(active.run_summary)
            save_run_summary(active.run_summary, settings)
        update_experiment_status(experiment_id, "stopped", settings)
        return dict(active.run_summary)

    run_summary = get_run_by_id(run_id, settings)
    if run_summary.get("experiment_id") != experiment_id:
        raise ValueError(f"Run not found: {run_id}")
    if run_summary["status"] != "running":
        raise ValueError(f"Run {run_id} is not running.")
    _mark_run_stopped(run_summary)
    save_run_summary(run_summary, settings)
    update_experiment_status(experiment_id, "stopped", settings)
    return run_summary


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
    output_format: str = "stl",
) -> dict[str, Any]:
    settings = settings or get_settings()
    experiment = get_experiment(experiment_id, settings)
    queries = experiment.get("queries", [])
    if not queries:
        raise ValueError(f"Experiment {experiment_id} has no queries to run.")
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    parameters = dict(parameters or {})
    output_format = str(parameters.pop("output_format", output_format))
    if output_format not in {"stl", "step"}:
        raise ValueError("output_format must be 'stl' or 'step'")
    default_model = model or experiment["setup"].get("model", "default")
    return_format = _resolve_return_format(parameters, experiment["setup"], settings)
    base_parameters = {
        "response_mode": parameters.get(
            "response_mode", experiment["setup"].get("response_mode", settings.default_response_mode)
        ),
        "return_format": return_format,
        "export_format": return_format,
        "linear_deflection": parameters.get(
            "linear_deflection",
            experiment["setup"].get("linear_deflection", settings.default_linear_deflection),
        ),
        "angular_deflection": parameters.get(
            "angular_deflection",
            experiment["setup"].get("angular_deflection", settings.default_angular_deflection),
        ),
        "concurrency": concurrency,
        "output_format": output_format,
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

    cancel_event = threading.Event()
    summary_lock = threading.Lock()
    active_run = _ActiveRun(
        experiment_id=experiment_id,
        cancel_event=cancel_event,
        lock=summary_lock,
        run_summary=run_summary,
    )
    _register_active_run(run_id, active_run)

    if on_event:
        on_event(
            "run_started",
            {"run_id": run_id, "experiment_id": experiment_id},
        )

    work_items = list(enumerate(queries))

    try:
        stopped = _run_query_work(
            experiment_id=experiment_id,
            run_id=run_id,
            run_summary=run_summary,
            work_items=work_items,
            base_parameters=base_parameters,
            default_model=default_model,
            output_format=output_format,
            client=client,
            settings=settings,
            cancel_event=cancel_event,
            summary_lock=summary_lock,
            on_event=on_event,
            concurrency=concurrency,
        )
    finally:
        _unregister_active_run(run_id)

    summary = run_summary.get("summary", {})
    return {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "run_ids": [run_id],
        "completed": summary.get("completed", 0),
        "failed": summary.get("failed", 0),
        "stopped": stopped,
    }


def _run_query_work(
    experiment_id: str,
    run_id: str,
    run_summary: dict[str, Any],
    work_items: list[tuple[int, dict[str, Any]]],
    base_parameters: dict[str, Any],
    default_model: str,
    output_format: str,
    client: CadybaraApiClient,
    settings: Settings,
    cancel_event: threading.Event,
    summary_lock: threading.Lock,
    on_event: Callable[[str, dict[str, Any]], None] | None,
    concurrency: int,
) -> bool:
    query_entries = run_summary["queries"]

    def execute_work_item(work_index: int, query: dict[str, Any]) -> None:
        query_entry = query_entries[work_index]

        with summary_lock:
            if cancel_event.is_set():
                if query_entry["status"] in {"pending", "running"}:
                    query_entry["status"] = "cancelled"
                    _sync_run_summary_counts(run_summary)
                    save_run_summary(run_summary, settings)
                return
            query_entry["status"] = "running"
            query_entry["error"] = {}
            save_run_summary(run_summary, settings)
        if on_event:
            on_event(
                "started",
                {"run_id": run_id, "query_id": query["id"]},
            )

        artifact_dir = run_dir(experiment_id, run_id, settings) / query["id"]
        artifact_dir.mkdir(parents=True, exist_ok=True)
        query_entry["artifact_dir"] = _stored_path(artifact_dir)

        try:
            query_model = query.get("model") or default_model
            full_parameters = {
                key: value
                for key, value in {**base_parameters, "model": query_model}.items()
                if key not in {"concurrency", "output_format"}
            }
            stored_images = query.get("images") or []
            api_images = load_api_images(stored_images)
            if api_images:
                full_parameters = {**full_parameters, "images": api_images}
            result = client.generate(query["text"], full_parameters)
            if cancel_event.is_set():
                query_entry["status"] = "cancelled"
            else:
                write_generate_artifacts(
                    artifact_dir,
                    result,
                    linear_deflection=base_parameters["linear_deflection"],
                    angular_deflection=base_parameters["angular_deflection"],
                    output_format=output_format,
                )
                query_entry["status"] = "completed"
                query_entry["response_metadata"] = result.response_metadata
                query_entry["metrics"] = result.raw_response.get("metrics", {})
                if on_event:
                    on_event(
                        "completed",
                        {"run_id": run_id, "query_id": query["id"]},
                    )
        except CadybaraApiError as exc:
            if cancel_event.is_set():
                query_entry["status"] = "cancelled"
            else:
                error_path = artifact_dir / "error.json"
                error_path.write_text(dumps_json(exc.payload))
                query_entry["status"] = "failed"
                query_entry["error"] = exc.payload
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
            if cancel_event.is_set():
                query_entry["status"] = "cancelled"
            else:
                error = {"message": str(exc), "type": exc.__class__.__name__}
                error_path = artifact_dir / "error.json"
                error_path.write_text(dumps_json(error))
                query_entry["status"] = "failed"
                query_entry["error"] = error
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
            _sync_run_summary_counts(run_summary)
            save_run_summary(run_summary, settings)

    worker_count = min(concurrency, len(work_items))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(execute_work_item, work_index, query)
            for work_index, query in work_items
        ]
        for future in futures:
            future.result()

    return _finalize_run_after_work(
        experiment_id,
        run_summary,
        cancel_event,
        summary_lock,
        settings,
    )


def _finalize_run_after_work(
    experiment_id: str,
    run_summary: dict[str, Any],
    cancel_event: threading.Event,
    summary_lock: threading.Lock,
    settings: Settings,
) -> bool:
    with summary_lock:
        _sync_run_summary_counts(run_summary)
        if cancel_event.is_set():
            _mark_run_stopped(run_summary)
            save_run_summary(run_summary, settings)
            update_experiment_status(experiment_id, "stopped", settings)
            return True

        queries = run_summary.get("queries", [])
        failed = any(query.get("status") == "failed" for query in queries)
        run_summary["status"] = "completed" if not failed else "completed_with_errors"
        run_summary["finished_at"] = utc_now()
        save_run_summary(run_summary, settings)
        update_experiment_status(experiment_id, run_summary["status"], settings)
        return False


def _sync_run_summary_counts(run_summary: dict[str, Any]) -> None:
    queries = run_summary.get("queries", [])
    completed = sum(1 for query in queries if query.get("status") == "completed")
    failed = sum(1 for query in queries if query.get("status") == "failed")
    run_summary["summary"] = {"completed": completed, "failed": failed}


def _register_active_run(run_id: str, active_run: _ActiveRun) -> None:
    with _active_runs_lock:
        _active_runs[run_id] = active_run


def _unregister_active_run(run_id: str) -> None:
    with _active_runs_lock:
        _active_runs.pop(run_id, None)


def _get_active_run(run_id: str) -> _ActiveRun | None:
    with _active_runs_lock:
        return _active_runs.get(run_id)


def _mark_run_stopped(run_summary: dict[str, Any]) -> None:
    for query_entry in run_summary.get("queries", []):
        if query_entry.get("status") in {"pending", "running"}:
            query_entry["status"] = "cancelled"
    run_summary["status"] = "stopped"
    run_summary["finished_at"] = utc_now()


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
        "status": "pending",
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


def _resolve_return_format(
    parameters: dict[str, Any],
    experiment_setup: dict[str, Any],
    settings: Settings,
) -> str:
    if parameters.get("return_format"):
        return str(parameters["return_format"])
    return str(experiment_setup.get("return_format", settings.default_return_format))


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
