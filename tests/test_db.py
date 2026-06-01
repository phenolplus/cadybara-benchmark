from __future__ import annotations

from cadybara_benchmark.db import connect, dumps_json, loads_json
from cadybara_benchmark.ids import next_id


def test_init_db_creates_tables(settings):
    with connect(settings) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()

    assert [row["name"] for row in rows] == ["experiments", "queries", "results", "runs"]


def test_next_id_starts_at_expected_value(settings):
    with connect(settings) as conn:
        assert next_id(conn, "experiments") == "EXP001"


def test_json_helpers_round_trip():
    value = {"b": 2, "a": [1]}
    assert loads_json(dumps_json(value)) == value
