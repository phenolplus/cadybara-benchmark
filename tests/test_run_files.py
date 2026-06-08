from __future__ import annotations

from cadybara_benchmark.json_utils import dumps_json, loads_json
from cadybara_benchmark.run_files import (
    get_run,
    list_runs,
    next_run_id,
    save_run_summary,
    summary_path,
)


def test_json_helpers_round_trip():
    value = {"b": 2, "a": [1]}
    assert loads_json(dumps_json(value)) == value


def test_save_and_load_run_summary(settings):
    summary = {
        "id": "RUN001",
        "experiment_id": "EXP001",
        "status": "completed",
        "started_at": "2026-06-07T00:00:00Z",
        "finished_at": "2026-06-07T00:01:00Z",
        "parameters": {"response_mode": "json"},
        "queries": [],
        "summary": {"completed": 0, "failed": 0},
    }
    path = save_run_summary(summary, settings)
    assert path == summary_path("EXP001", "RUN001", settings)
    loaded = get_run("EXP001", "RUN001", settings)
    assert loaded == summary


def test_list_runs_sorted(settings):
    for run_id in ("RUN002", "RUN001"):
        save_run_summary(
            {
                "id": run_id,
                "experiment_id": "EXP001",
                "status": "completed",
                "started_at": "",
                "finished_at": "",
                "parameters": {},
                "queries": [],
                "summary": {"completed": 0, "failed": 0},
            },
            settings,
        )
    assert [run["id"] for run in list_runs("EXP001", settings)] == ["RUN001", "RUN002"]


def test_next_run_id(settings):
    assert next_run_id("EXP001", settings) == "RUN001"
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "completed",
            "started_at": "",
            "finished_at": "",
            "parameters": {},
            "queries": [],
            "summary": {"completed": 0, "failed": 0},
        },
        settings,
    )
    assert next_run_id("EXP001", settings) == "RUN002"
