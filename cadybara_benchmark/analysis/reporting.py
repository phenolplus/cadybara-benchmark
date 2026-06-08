from __future__ import annotations

from typing import Any

from cadybara_benchmark.config import Settings
from cadybara_benchmark.services.queries import list_queries
from cadybara_benchmark.services.runs import list_runs


def generate_report(experiment_id: str, settings: Settings | None = None) -> dict[str, Any]:
    queries = list_queries(experiment_id, settings)
    runs = list_runs(experiment_id, settings)
    completed_runs = len([run for run in runs if run["status"] == "completed"])
    failed_runs = len([run for run in runs if run["status"] in {"failed", "completed_with_errors"}])
    query_results = []
    for run in runs:
        for query in run.get("queries", []):
            if query.get("status") == "completed":
                query_results.append(query)
    scored = [query for query in query_results if query.get("score") is not None]
    average = sum(query["score"] for query in scored) / len(scored) if scored else None
    return {
        "experiment_id": experiment_id,
        "summary": {
            "query_count": len(queries),
            "run_count": len(runs),
            "query_result_count": len(query_results),
            "completed_count": completed_runs,
            "failed_count": failed_runs,
            "average_overall_score": average,
        },
        "results": [
            {
                "result_id": f"{run['id']}:{query['query_id']}",
                "run_id": run["id"],
                "query_id": query["query_id"],
                "score": query.get("score"),
            }
            for run in runs
            for query in run.get("queries", [])
            if query.get("status") == "completed"
        ],
        "charts": [],
        "statistics": [],
    }
