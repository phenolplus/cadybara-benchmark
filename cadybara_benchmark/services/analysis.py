from __future__ import annotations

from typing import Any

from cadybara_benchmark.analysis.artifacts import inspect_artifacts
from cadybara_benchmark.analysis.parsing import parse_output
from cadybara_benchmark.analysis.reporting import generate_report
from cadybara_benchmark.analysis.scoring import score_result
from cadybara_benchmark.config import Settings, get_settings
from cadybara_benchmark.db import connect, dumps_json
from cadybara_benchmark.services.queries import get_query
from cadybara_benchmark.services.runs import list_results_for_experiment, list_runs


def analyze_experiment(experiment_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    runs = {run["id"]: run for run in list_runs(experiment_id, settings)}
    results = list_results_for_experiment(experiment_id, settings)
    updated = []

    with connect(settings) as conn:
        for result in results:
            run = runs[result["run_id"]]
            query = get_query(run["query_id"], settings)
            output = parse_output(result["raw_output"])
            artifacts = inspect_artifacts(result["stl_paths"])
            metrics = score_result(query, output, artifacts)
            conn.execute(
                "UPDATE results SET score = ?, metrics = ? WHERE id = ?",
                (metrics["overall"], dumps_json(metrics), result["id"]),
            )
            updated.append({"result_id": result["id"], "run_id": result["run_id"], "metrics": metrics})

    report = generate_report(experiment_id, settings)
    report["updated_results"] = updated
    report_dir = settings.workspace_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{experiment_id}.json"
    report_path.write_text(dumps_json(report))
    report["report_path"] = str(report_path.relative_to(settings.workspace_dir.parent))
    return report
