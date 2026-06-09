from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cadybara_benchmark.config import Settings, get_settings


def experiment_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.workspace_dir / "experiments"


def experiment_path(experiment_id: str, settings: Settings | None = None) -> Path:
    return experiment_dir(settings) / f"{experiment_id}.yaml"


def list_experiment_files(settings: Settings | None = None) -> list[Path]:
    directory = experiment_dir(settings)
    if not directory.exists():
        return []
    return sorted(directory.glob("EXP*.yaml"))


def load_experiment(experiment_id: str, settings: Settings | None = None) -> dict[str, Any]:
    path = experiment_path(experiment_id, settings)
    if not path.exists():
        raise ValueError(f"Experiment not found: {experiment_id}")
    return loads_experiment_yaml(path.read_text())


def load_experiments(settings: Settings | None = None) -> list[dict[str, Any]]:
    return [loads_experiment_yaml(path.read_text()) for path in list_experiment_files(settings)]


def save_experiment(experiment: dict[str, Any], settings: Settings | None = None) -> Path:
    path = experiment_path(experiment["id"], settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_experiment_yaml(experiment))
    return path


def dumps_experiment_yaml(experiment: dict[str, Any]) -> str:
    lines = [
        f"id: {_format_scalar(experiment['id'])}",
        f"name: {_format_scalar(experiment.get('name', ''))}",
        f"description: {_format_scalar(experiment.get('description', ''))}",
        f"type: {_format_scalar(experiment.get('type', ''))}",
        f"status: {_format_scalar(experiment.get('status', ''))}",
        "setup:",
    ]
    for key, value in experiment.get("setup", {}).items():
        lines.append(f"  {key}: {_format_scalar(value)}")
    lines.extend(
        [
            f"created_at: {_format_scalar(experiment.get('created_at', ''))}",
            f"updated_at: {_format_scalar(experiment.get('updated_at', ''))}",
            "queries:",
        ]
    )
    for query in experiment.get("queries", []):
        lines.extend(
            [
                f"  - id: {_format_scalar(query['id'])}",
                f"    text: {_format_scalar(query.get('text', ''))}",
                f"    model: {_format_scalar(query.get('model', ''))}",
                f"    category: {_format_scalar(query.get('category', ''))}",
                f"    metadata: {_format_scalar(query.get('metadata', {}))}",
            ]
        )
        images = query.get("images") or []
        if images:
            lines.append(f"    images: {_format_scalar(images)}")
    return "\n".join(lines) + "\n"


def loads_experiment_yaml(content: str) -> dict[str, Any]:
    experiment: dict[str, Any] = {}
    setup: dict[str, Any] = {}
    queries: list[dict[str, Any]] = []
    current_section: str | None = None
    current_query: dict[str, Any] | None = None

    for raw_line in content.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - "):
            current_section = "queries"
            key, value = _split_key_value(raw_line[4:])
            current_query = {key: _parse_scalar(value)}
            queries.append(current_query)
            continue
        if raw_line.startswith("    "):
            if current_section != "queries" or current_query is None:
                raise ValueError("Invalid experiment YAML query field.")
            key, value = _split_key_value(raw_line[4:])
            current_query[key] = _parse_scalar(value)
            continue
        if raw_line.startswith("  "):
            if current_section != "setup":
                raise ValueError("Invalid experiment YAML nested field.")
            key, value = _split_key_value(raw_line[2:])
            setup[key] = _parse_scalar(value)
            continue

        key, value = _split_key_value(raw_line)
        if value == "":
            current_section = key
            if key not in {"setup", "queries"}:
                raise ValueError(f"Unsupported experiment YAML section: {key}")
            continue
        current_section = None
        experiment[key] = _parse_scalar(value)

    experiment["setup"] = setup
    experiment["queries"] = queries
    return experiment


def _split_key_value(line: str) -> tuple[str, str]:
    if ":" not in line:
        raise ValueError(f"Invalid experiment YAML line: {line}")
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _format_scalar(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _parse_scalar(value: str) -> Any:
    if value == "":
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
