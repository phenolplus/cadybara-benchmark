from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from cadybara_benchmark.config import Settings, get_settings
from cadybara_benchmark.json_utils import dumps_json, loads_json


RUN_ID_PATTERN = re.compile(r"^RUN(\d+)$")


def artifacts_dir(experiment_id: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.workspace_dir / "artifacts" / experiment_id


def run_dir(experiment_id: str, run_id: str, settings: Settings | None = None) -> Path:
    return artifacts_dir(experiment_id, settings) / run_id


def summary_path(experiment_id: str, run_id: str, settings: Settings | None = None) -> Path:
    return run_dir(experiment_id, run_id, settings) / "summary.json"


def load_run_summary(path: Path) -> dict[str, Any]:
    return loads_json(path.read_text())


def save_run_summary(summary: dict[str, Any], settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    path = summary_path(summary["experiment_id"], summary["id"], settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(dumps_json(summary))
    temp_path.replace(path)
    return path


def list_runs(experiment_id: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    directory = artifacts_dir(experiment_id, settings)
    if not directory.exists():
        return []

    runs: list[dict[str, Any]] = []
    for run_path in sorted(directory.iterdir()):
        if not run_path.is_dir():
            continue
        summary_file = run_path / "summary.json"
        if not summary_file.exists():
            continue
        runs.append(load_run_summary(summary_file))
    return sorted(runs, key=lambda run: run["id"])


def get_run(experiment_id: str, run_id: str, settings: Settings | None = None) -> dict[str, Any]:
    path = summary_path(experiment_id, run_id, settings)
    if not path.exists():
        raise ValueError(f"Run not found: {run_id}")
    return load_run_summary(path)


def get_run_by_id(run_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    artifacts_root = settings.workspace_dir / "artifacts"
    if not artifacts_root.exists():
        raise ValueError(f"Run not found: {run_id}")

    for experiment_dir in artifacts_root.iterdir():
        if not experiment_dir.is_dir():
            continue
        path = experiment_dir / run_id / "summary.json"
        if path.exists():
            return load_run_summary(path)
    raise ValueError(f"Run not found: {run_id}")


def next_run_id(experiment_id: str, settings: Settings | None = None) -> str:
    directory = artifacts_dir(experiment_id, settings)
    highest = 0
    if directory.exists():
        for run_path in directory.iterdir():
            if not run_path.is_dir():
                continue
            match = RUN_ID_PATTERN.match(run_path.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return f"RUN{highest + 1:03d}"
