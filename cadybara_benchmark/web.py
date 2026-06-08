from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cadybara_benchmark.config import REPO_ROOT, get_settings
from cadybara_benchmark.publishing import publish_experiment
from cadybara_benchmark.services.experiments import (
    create_experiment,
    get_experiment,
    list_experiments,
)
from cadybara_benchmark.services.queries import add_query, list_queries
from cadybara_benchmark.run_files import get_run
from cadybara_benchmark.services.runs import (
    list_results_for_experiment,
    list_runs,
    run_experiment,
)


PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"

app = FastAPI(title="Cadybara Benchmark Webapp")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    type: str = "query_comparison"
    setup: dict[str, Any] | None = None


class QueryCreate(BaseModel):
    text: str = Field(min_length=1)
    sublabel: str | None = None
    model: str | None = None
    category: str | None = None
    metadata: dict[str, Any] | None = None


class RunRequest(BaseModel):
    model: str | None = None
    parameters: dict[str, Any] | None = None


@app.get("/", response_class=HTMLResponse)
@app.get("/experiments", response_class=HTMLResponse)
@app.get("/experiment/{experiment_id}", response_class=HTMLResponse)
@app.get("/published", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text())


@app.get("/view/{experiment_id}/{run_id}/{query_id}", response_class=HTMLResponse)
def stl_viewer() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "stl-viewer.html").read_text())


@app.get("/compare/{experiment_id}/{run_id}", response_class=HTMLResponse)
def compare_viewer() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "compare.html").read_text())


@app.get("/api/experiments")
def api_list_experiments() -> list[dict[str, Any]]:
    return [_experiment_summary(experiment) for experiment in list_experiments()]


@app.post("/api/experiments", status_code=201)
def api_create_experiment(payload: ExperimentCreate) -> dict[str, Any]:
    try:
        return create_experiment(
            payload.name,
            payload.description,
            payload.type,
            setup=payload.setup,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/experiments/{experiment_id}")
def api_get_experiment(experiment_id: str) -> dict[str, Any]:
    try:
        experiment = get_experiment(experiment_id)
        runs = [_with_run_stats(run) for run in list_runs(experiment_id)]
        results = list_results_for_experiment(experiment_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {
        **experiment,
        "queries": list_queries(experiment_id),
        "runs": runs,
        "results": results,
    }


@app.post("/api/experiments/{experiment_id}/queries", status_code=201)
def api_add_query(experiment_id: str, payload: QueryCreate) -> dict[str, Any]:
    try:
        return add_query(
            experiment_id,
            payload.text,
            category=payload.category,
            model=payload.model,
            sublabel=payload.sublabel,
            metadata=payload.metadata,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/experiments/{experiment_id}/run")
def api_run_experiment(experiment_id: str, payload: RunRequest) -> dict[str, Any]:
    try:
        get_settings().require_api_key()
        return run_experiment(experiment_id, payload.model, payload.parameters)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/experiments/{experiment_id}/publish")
def api_publish_experiment(experiment_id: str, run_id: str | None = None) -> dict[str, Any]:
    try:
        return publish_experiment(experiment_id, run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/experiments/{experiment_id}/runs/{run_id}")
def api_get_run(experiment_id: str, run_id: str) -> dict[str, Any]:
    try:
        return _run_payload(experiment_id, run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/experiments/{experiment_id}/runs/{run_id}/queries/{query_id}")
def api_get_run_query(experiment_id: str, run_id: str, query_id: str) -> dict[str, Any]:
    try:
        return _run_query(experiment_id, run_id, query_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/experiments/{experiment_id}/runs/{run_id}/queries/{query_id}/stl")
def api_get_run_query_stl(experiment_id: str, run_id: str, query_id: str) -> FileResponse:
    try:
        stl_path = _query_stl_path(experiment_id, run_id, query_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    if not stl_path.exists():
        raise HTTPException(status_code=404, detail="STL artifact not found.")
    return FileResponse(stl_path, media_type="model/stl", filename="model.stl")


@app.get("/api/published")
def api_list_published() -> list[dict[str, Any]]:
    settings = get_settings()
    published_dir = settings.published_dir / "runs"
    if not published_dir.exists():
        return []

    published = []
    for path in sorted(published_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        payload["file_path"] = _stored_path(path)
        published.append(payload)
    return sorted(published, key=lambda item: item.get("published_at", ""), reverse=True)


def _experiment_summary(experiment: dict[str, Any]) -> dict[str, Any]:
    experiment_id = experiment["id"]
    try:
        runs = list_runs(experiment_id)
        results = list_results_for_experiment(experiment_id)
    except Exception:
        runs = []
        results = []
    return {
        **experiment,
        "query_count": len(experiment.get("queries", [])),
        "run_count": len(runs),
        "result_count": len(results),
    }


def _with_run_stats(run: dict[str, Any]) -> dict[str, Any]:
    queries = run.get("queries", [])
    completed = len([query for query in queries if query.get("status") == "completed"])
    failed = len([query for query in queries if query.get("status") == "failed"])
    scores = [query["score"] for query in queries if query.get("score") is not None]
    average_score = sum(scores) / len(scores) if scores else None
    return {
        **run,
        "query_count": len(queries),
        "completed_count": completed,
        "failed_count": failed,
        "average_score": average_score,
    }


def _http_error(exc: Exception) -> HTTPException:
    message = str(exc) or exc.__class__.__name__
    status_code = 404 if isinstance(exc, ValueError) and "not found" in message.lower() else 400
    return HTTPException(status_code=status_code, detail=message)


def _stored_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _run_payload(experiment_id: str, run_id: str) -> dict[str, Any]:
    run = get_run(experiment_id, run_id)
    queries = []
    for query in run.get("queries", []):
        stl_path = _resolve_query_stl_path(query)
        queries.append(
            {
                **query,
                "has_stl": bool(stl_path and stl_path.exists()),
            }
        )
    return {
        **run,
        "experiment_id": experiment_id,
        "queries": queries,
    }


def _run_query(experiment_id: str, run_id: str, query_id: str) -> dict[str, Any]:
    run = get_run(experiment_id, run_id)
    query = _find_run_query(run, query_id)
    stl_path = _resolve_query_stl_path(query)
    return {
        **query,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "has_stl": bool(stl_path and stl_path.exists()),
    }


def _find_run_query(run: dict[str, Any], query_id: str) -> dict[str, Any]:
    for query in run.get("queries", []):
        if query.get("query_id") == query_id:
            return query
    raise ValueError(f"Query not found: {query_id}")


def _query_stl_path(experiment_id: str, run_id: str, query_id: str) -> Path:
    run = get_run(experiment_id, run_id)
    query = _find_run_query(run, query_id)
    stl_path = _resolve_query_stl_path(query)
    if stl_path is None:
        raise ValueError(f"Query {query_id} has no STL artifact.")
    return stl_path


def _resolve_query_stl_path(query: dict[str, Any]) -> Path | None:
    if query.get("status") != "completed":
        return None
    artifact_dir = _resolve_path(query["artifact_dir"])
    _ensure_workspace_path(artifact_dir)
    return artifact_dir / "model.stl"


def _resolve_path(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate


def _ensure_workspace_path(path: Path) -> None:
    workspace = get_settings().workspace_dir.resolve()
    resolved = path.resolve()
    if resolved != workspace and workspace not in resolved.parents:
        raise ValueError("Artifact path is outside the workspace.")
