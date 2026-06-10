from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Literal

from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings
from cadybara_benchmark.experiment_files import load_experiment
from cadybara_benchmark.geometry import render_code_to_step
from cadybara_benchmark.json_utils import dumps_json
from cadybara_benchmark.run_files import get_run


CadGenBenchExportSeries = Literal["100", "200", "both"]

_SERIES_RANGES: dict[CadGenBenchExportSeries, range] = {
    "100": range(100, 200),
    "200": range(200, 300),
}


def export_cadgenbench_submission(
    experiment_id: str,
    run_id: str,
    destination: Path,
    *,
    series: CadGenBenchExportSeries = "both",
    submitter_name: str = "Cadybara Benchmark",
    submission_name: str | None = None,
    agent_url: str | None = None,
    notes: str | None = None,
    agree_to_publish: bool = True,
    render_step: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    experiment = load_experiment(experiment_id, settings)
    run = get_run(experiment_id, run_id, settings)
    selected_series = _normalize_series(series)

    destination = destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    queries = _selected_run_queries(experiment, run, selected_series)
    if not queries:
        raise ValueError("No CadGenBench run queries matched the requested series.")

    meta = _build_meta(
        experiment=experiment,
        run=run,
        series=series,
        submitter_name=submitter_name,
        submission_name=submission_name,
        agent_url=agent_url,
        notes=notes,
        agree_to_publish=agree_to_publish,
    )
    (destination / "meta.json").write_text(dumps_json(meta) + "\n")

    exported: list[dict[str, Any]] = []
    for item in queries:
        sample_dir = destination / item["sample_id"]
        sample_dir.mkdir(parents=True, exist_ok=True)
        output_path = _export_query_step(
            item["run_query"],
            sample_dir,
            render_step=render_step,
        )
        exported.append(
            {
                "sample_id": item["sample_id"],
                "query_id": item["run_query"].get("query_id", ""),
                "status": item["run_query"].get("status", ""),
                "output_step": str(output_path) if output_path else "",
            }
        )

    return {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "destination": str(destination),
        "series": series,
        "render_step": render_step,
        "exported": exported,
        "count": len(exported),
        "with_output_step": sum(1 for item in exported if item["output_step"]),
    }


def _selected_run_queries(
    experiment: dict[str, Any],
    run: dict[str, Any],
    series: list[Literal["100", "200"]],
) -> list[dict[str, Any]]:
    experiment_queries = {
        str(query["id"]): query for query in experiment.get("queries", [])
    }
    selected: list[dict[str, Any]] = []
    for run_query in run.get("queries", []):
        query_id = str(run_query.get("query_id", ""))
        experiment_query = experiment_queries.get(query_id)
        sample_id = _sample_id(query_id, experiment_query)
        sample_series = _series_for_sample_id(sample_id)
        if sample_series not in series:
            continue
        selected.append(
            {
                "sample_id": sample_id,
                "series": sample_series,
                "run_query": run_query,
                "experiment_query": experiment_query or {},
            }
        )
    return selected


def _sample_id(query_id: str, experiment_query: dict[str, Any] | None) -> str:
    metadata = (experiment_query or {}).get("metadata") or {}
    folder_id = metadata.get("folder_id")
    if folder_id is not None:
        return str(folder_id)
    return query_id


def _series_for_sample_id(sample_id: str) -> Literal["100", "200"]:
    if not sample_id.isdigit():
        raise ValueError(f"CadGenBench sample id must be numeric: {sample_id}")
    sample_number = int(sample_id)
    for series, sample_range in _SERIES_RANGES.items():
        if sample_number in sample_range:
            return series  # type: ignore[return-value]
    raise ValueError(f"Unsupported CadGenBench sample id: {sample_id}")


def _export_query_step(
    run_query: dict[str, Any],
    sample_dir: Path,
    *,
    render_step: bool,
) -> Path | None:
    artifact_dir_value = str(run_query.get("artifact_dir") or "")
    if run_query.get("status") != "completed" or not artifact_dir_value:
        return None

    artifact_dir = _resolve_path(artifact_dir_value)
    generated_code_path = artifact_dir / "generated_code.py"
    if render_step and generated_code_path.exists():
        output_path = sample_dir / "output.step"
        output_path.write_bytes(render_code_to_step(generated_code_path.read_text()))
        return output_path

    step_path = artifact_dir / "model.step"
    if step_path.exists():
        output_path = sample_dir / "output.step"
        shutil.copyfile(step_path, output_path)
        return output_path

    return None


def _build_meta(
    *,
    experiment: dict[str, Any],
    run: dict[str, Any],
    series: str,
    submitter_name: str,
    submission_name: str | None,
    agent_url: str | None,
    notes: str | None,
    agree_to_publish: bool,
) -> dict[str, Any]:
    return {
        "submitter_name": submitter_name,
        "submission_name": submission_name or f"{experiment.get('name', experiment['id'])} {run['id']}",
        "agent_url": agent_url,
        "notes": notes,
        "agree_to_publish": agree_to_publish,
        "series": series,
        "experiment_id": experiment["id"],
        "run_id": run["id"],
        "model": (experiment.get("setup") or {}).get("model", ""),
    }


def _normalize_series(series: str) -> list[Literal["100", "200"]]:
    if series == "both":
        return ["100", "200"]
    if series in {"100", "200"}:
        return [series]  # type: ignore[list-item]
    raise ValueError("Series must be 100, 200, or both.")


def _resolve_path(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate
