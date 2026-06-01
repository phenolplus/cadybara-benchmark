from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cadybara_benchmark.api_client import CadybaraApiClient, CadybaraApiError
from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings
from cadybara_benchmark.db import connect, dumps_json, row_to_dict, rows_to_dicts
from cadybara_benchmark.ids import next_id
from cadybara_benchmark.services.experiments import get_experiment, update_experiment_status
from cadybara_benchmark.services.queries import list_queries
from cadybara_benchmark.time import utc_now


def list_runs(experiment_id: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    with connect(settings) as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE experiment_id = ? ORDER BY id", (experiment_id,)
        ).fetchall()
        return rows_to_dicts(rows, "runs")


def get_run(run_id: str, settings: Settings | None = None) -> dict[str, Any]:
    with connect(settings) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        run = row_to_dict(row, "runs")
    if run is None:
        raise ValueError(f"Run not found: {run_id}")
    return run


def list_results_for_experiment(
    experiment_id: str, settings: Settings | None = None
) -> list[dict[str, Any]]:
    with connect(settings) as conn:
        rows = conn.execute(
            """
            SELECT results.*
            FROM results
            JOIN runs ON runs.id = results.run_id
            WHERE runs.experiment_id = ?
            ORDER BY results.id
            """,
            (experiment_id,),
        ).fetchall()
        return rows_to_dicts(rows, "results")


def run_experiment(
    experiment_id: str,
    model: str = "default",
    parameters: dict[str, Any] | None = None,
    client: CadybaraApiClient | None = None,
    settings: Settings | None = None,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    experiment = get_experiment(experiment_id, settings)
    queries = list_queries(experiment_id, settings)
    if not queries:
        raise ValueError(f"Experiment {experiment_id} has no queries to run.")

    parameters = parameters or {}
    full_parameters = {
        "response_mode": parameters.get(
            "response_mode", experiment["setup"].get("response_mode", settings.default_response_mode)
        ),
        "model": model,
        "linear_deflection": parameters.get(
            "linear_deflection",
            experiment["setup"].get("linear_deflection", settings.default_linear_deflection),
        ),
        "angular_deflection": parameters.get(
            "angular_deflection",
            experiment["setup"].get("angular_deflection", settings.default_angular_deflection),
        ),
    }
    client = client or CadybaraApiClient(settings)
    update_experiment_status(experiment_id, "running", settings)

    completed = 0
    failed = 0
    run_ids: list[str] = []

    for query in queries:
        run_id = _create_run(experiment_id, query["id"], model, full_parameters, settings)
        run_ids.append(run_id)
        if on_event:
            on_event("started", {"run_id": run_id, "query_id": query["id"]})
        artifact_dir = settings.workspace_dir / "artifacts" / experiment_id / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = client.generate(query["text"], full_parameters)
            stl_path = artifact_dir / "model.stl"
            stl_path.write_bytes(result.stl_bytes)
            response_path = artifact_dir / "response.json"
            response_path.write_text(dumps_json(result.raw_response))
            artifact_paths = [_stored_path(response_path)]
            if result.generated_code:
                code_path = artifact_dir / "generated_code.py"
                code_path.write_text(result.generated_code)
                artifact_paths.append(_stored_path(code_path))
            _create_result(
                run_id,
                result.response_metadata,
                result.raw_response,
                [_stored_path(stl_path)],
                artifact_paths,
                settings,
            )
            _finish_run(run_id, "completed", None, settings)
            completed += 1
            if on_event:
                on_event("completed", {"run_id": run_id, "query_id": query["id"]})
        except CadybaraApiError as exc:
            error_path = artifact_dir / "error.json"
            error_path.write_text(dumps_json(exc.payload))
            _finish_run(run_id, "failed", exc.payload, settings)
            failed += 1
            if on_event:
                on_event("failed", {"run_id": run_id, "query_id": query["id"], "error": exc.payload})
        except Exception as exc:
            error = {"message": str(exc), "type": exc.__class__.__name__}
            error_path = artifact_dir / "error.json"
            error_path.write_text(dumps_json(error))
            _finish_run(run_id, "failed", error, settings)
            failed += 1
            if on_event:
                on_event("failed", {"run_id": run_id, "query_id": query["id"], "error": error})

    update_experiment_status(experiment_id, "completed" if failed == 0 else "completed_with_errors", settings)
    return {"experiment_id": experiment_id, "run_ids": run_ids, "completed": completed, "failed": failed}


def _create_run(
    experiment_id: str,
    query_id: str,
    model: str,
    parameters: dict[str, Any],
    settings: Settings,
) -> str:
    now = utc_now()
    with connect(settings) as conn:
        run_id = next_id(conn, "runs")
        conn.execute(
            """
            INSERT INTO runs (id, experiment_id, query_id, model, parameters, status, started_at, finished_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                experiment_id,
                query_id,
                model,
                dumps_json(parameters),
                "running",
                now,
                "",
                dumps_json({}),
            ),
        )
    return run_id


def _finish_run(
    run_id: str,
    status: str,
    error: dict[str, Any] | None,
    settings: Settings,
) -> None:
    with connect(settings) as conn:
        conn.execute(
            "UPDATE runs SET status = ?, finished_at = ?, error = ? WHERE id = ?",
            (status, utc_now(), dumps_json(error or {}), run_id),
        )


def _create_result(
    run_id: str,
    response_metadata: dict[str, Any],
    raw_output: dict[str, Any],
    stl_paths: list[str],
    artifact_paths: list[str],
    settings: Settings,
) -> str:
    with connect(settings) as conn:
        result_id = next_id(conn, "results")
        conn.execute(
            """
            INSERT INTO results (id, run_id, response_metadata, score, metrics, raw_output, stl_paths, artifact_paths)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result_id,
                run_id,
                dumps_json(response_metadata),
                None,
                dumps_json({}),
                dumps_json(raw_output),
                dumps_json(stl_paths),
                dumps_json(artifact_paths),
            ),
        )
    return result_id


def get_result_for_run(run_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with connect(settings) as conn:
        row = conn.execute("SELECT * FROM results WHERE run_id = ?", (run_id,)).fetchone()
        return row_to_dict(row, "results")


def _stored_path(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
