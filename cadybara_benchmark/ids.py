from __future__ import annotations

import re

from cadybara_benchmark.config import Settings
from cadybara_benchmark.experiment_files import list_experiment_files
from cadybara_benchmark.run_files import next_run_id


def next_experiment_id(settings: Settings | None = None) -> str:
    highest = 0
    pattern = re.compile(r"^EXP(\d+)\.yaml$")
    for path in list_experiment_files(settings):
        match = pattern.match(path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"EXP{highest + 1:03d}"


def next_query_id(experiment: dict) -> str:
    highest = 0
    pattern = re.compile(r"^Q(\d+)$")
    for query in experiment.get("queries", []):
        match = pattern.match(query["id"])
        if match:
            highest = max(highest, int(match.group(1)))
    return f"Q{highest + 1:03d}"


__all__ = ["next_experiment_id", "next_query_id", "next_run_id"]
