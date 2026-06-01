from __future__ import annotations

from cadybara_benchmark.services.experiments import create_experiment, get_experiment
from cadybara_benchmark.services.queries import add_query, list_queries


def test_create_experiment_stores_default_setup(settings):
    experiment = create_experiment("Bracket Query Comparison", settings=settings)

    assert experiment["id"] == "EXP001"
    assert experiment["status"] == "draft"
    assert experiment["setup"]["response_mode"] == "json"


def test_add_query_validates_and_lists(settings):
    create_experiment("Bracket Query Comparison", settings=settings)
    query = add_query("EXP001", "Create a cube.", "mechanical", settings=settings)

    assert query["id"] == "Q001"
    assert list_queries("EXP001", settings)[0]["text"] == "Create a cube."
    assert get_experiment("EXP001", settings)["name"] == "Bracket Query Comparison"
