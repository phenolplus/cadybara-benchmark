from __future__ import annotations

import re
import sqlite3


ID_SPECS = {
    "experiments": ("EXP", "id"),
    "queries": ("Q", "id"),
    "runs": ("RUN", "id"),
    "results": ("RES", "id"),
}


def next_id(conn: sqlite3.Connection, table: str) -> str:
    if table not in ID_SPECS:
        raise ValueError(f"Unsupported ID table: {table}")
    prefix, column = ID_SPECS[table]
    rows = conn.execute(f"SELECT {column} FROM {table}").fetchall()
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    highest = 0
    for row in rows:
        match = pattern.match(row[column])
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}{highest + 1:03d}"
