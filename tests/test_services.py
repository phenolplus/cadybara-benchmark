from __future__ import annotations

from cadybara_benchmark.services.experiments import create_experiment, get_experiment
from cadybara_benchmark.services.queries import add_query, get_query, list_queries


def test_create_experiment_stores_default_setup(settings):
    experiment = create_experiment("Bracket Query Comparison", settings=settings)

    assert experiment["id"] == "EXP001"
    assert experiment["status"] == "draft"
    assert experiment["setup"]["response_mode"] == "json"
    assert experiment["setup"]["return_format"] == "code"
    assert (settings.workspace_dir / "experiments" / "EXP001.yaml").exists()


def test_add_query_validates_and_lists(settings):
    create_experiment("Bracket Query Comparison", settings=settings)
    query = add_query(
        "EXP001",
        "Create a cube.",
        "mechanical",
        model="google/gemini-3-flash-preview",
        settings=settings,
    )

    assert query["id"] == "Q001"
    assert query["model"] == "google/gemini-3-flash-preview"
    assert list_queries("EXP001", settings)[0]["text"] == "Create a cube."
    assert list_queries("EXP001", settings)[0]["model"] == "google/gemini-3-flash-preview"
    assert get_experiment("EXP001", settings)["name"] == "Bracket Query Comparison"
    assert get_experiment("EXP001", settings)["queries"][0]["id"] == "Q001"


def test_get_query_can_scope_duplicate_query_ids(settings):
    create_experiment("First", settings=settings)
    create_experiment("Second", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    add_query("EXP002", "Create a sphere.", settings=settings)

    query = get_query("Q001", settings, experiment_id="EXP002")

    assert query["text"] == "Create a sphere."
