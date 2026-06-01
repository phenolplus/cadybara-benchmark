from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings


JSON_FIELDS = {
    "experiments": {"setup"},
    "queries": {"metadata"},
    "runs": {"parameters", "error"},
    "results": {"response_metadata", "metrics", "raw_output", "stl_paths", "artifact_paths"},
}


def dumps_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def loads_json(value: str | None, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    return json.loads(value)


def schema_path() -> Path:
    return REPO_ROOT / "database" / "schema.sql"


def init_db(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.db_path) as conn:
        conn.executescript(schema_path().read_text())
    return settings.db_path


def ensure_db(settings: Settings | None = None) -> Path:
    return init_db(settings)


@contextmanager
def connect(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    settings = settings or get_settings()
    ensure_db(settings)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None, table: str) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for field in JSON_FIELDS.get(table, set()):
        if field in data:
            default: Any = [] if field.endswith("_paths") else {}
            data[field] = loads_json(data[field], default)
    return data


def rows_to_dicts(rows: list[sqlite3.Row], table: str) -> list[dict[str, Any]]:
    return [row_to_dict(row, table) for row in rows if row is not None]
