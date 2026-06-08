from __future__ import annotations

from pathlib import Path
from typing import Any

from cadybara_benchmark.analysis.artifacts import inspect_artifacts
from cadybara_benchmark.analysis.parsing import parse_output
from cadybara_benchmark.analysis.reporting import generate_report
from cadybara_benchmark.analysis.scoring import score_result
from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings
from cadybara_benchmark.json_utils import dumps_json, loads_json
from cadybara_benchmark.run_files import save_run_summary
from cadybara_benchmark.services.runs import list_runs


def analyze_experiment(experiment_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    updated = []

    for run in list_runs(experiment_id, settings):
        for query in run.get("queries", []):
            if query.get("status") != "completed":
                continue
            artifact_dir = _resolve_path(query["artifact_dir"])
            response_path = artifact_dir / "response.json"
            stl_path = artifact_dir / "model.stl"
            raw_output = loads_json(response_path.read_text(), {}) if response_path.exists() else {}
            query_payload = {
                "experiment_id": run["experiment_id"],
                "sublabel": query.get("sublabel", ""),
                "text": query.get("text", ""),
                "model": query.get("model", ""),
            }
            output = parse_output(raw_output)
            artifacts = inspect_artifacts([_stored_path(stl_path)] if stl_path.exists() else [])
            metrics = score_result(query_payload, output, artifacts)
            query["score"] = metrics["overall"]
            query["metrics"] = metrics
            updated.append(
                {
                    "result_id": f"{run['id']}:{query['query_id']}",
                    "run_id": run["id"],
                    "query_id": query["query_id"],
                    "metrics": metrics,
                }
            )
        save_run_summary(run, settings)

    report = generate_report(experiment_id, settings)
    report["updated_results"] = updated
    report_dir = settings.workspace_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{experiment_id}.json"
    report_path.write_text(dumps_json(report))
    report["report_path"] = str(report_path.relative_to(settings.workspace_dir.parent))
    return report


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
