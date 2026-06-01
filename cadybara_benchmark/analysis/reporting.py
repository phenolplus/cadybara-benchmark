from __future__ import annotations

from typing import Any

from cadybara_benchmark.config import Settings
from cadybara_benchmark.services.queries import list_queries
from cadybara_benchmark.services.runs import list_results_for_experiment, list_runs


def generate_report(experiment_id: str, settings: Settings | None = None) -> dict[str, Any]:
    queries = list_queries(experiment_id, settings)
    runs = list_runs(experiment_id, settings)
    results = list_results_for_experiment(experiment_id, settings)
    completed = len([run for run in runs if run["status"] == "completed"])
    failed = len([run for run in runs if run["status"] == "failed"])
    scored = [result for result in results if result["score"] is not None]
    average = sum(result["score"] for result in scored) / len(scored) if scored else None
    return {
        "experiment_id": experiment_id,
        "summary": {
            "query_count": len(queries),
            "run_count": len(runs),
            "completed_count": completed,
            "failed_count": failed,
            "average_overall_score": average,
        },
        "results": [{"result_id": result["id"], "run_id": result["run_id"], "score": result["score"]} for result in results],
        "charts": [],
        "statistics": [],
    }
