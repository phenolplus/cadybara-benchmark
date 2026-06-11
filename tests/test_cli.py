from __future__ import annotations

from typer.testing import CliRunner

from cadybara_benchmark.cli import app
from cadybara_benchmark.experiment_files import load_experiment


runner = CliRunner()


def test_cli_create_and_add_query(tmp_path, monkeypatch):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))

    result = runner.invoke(app, ["create-experiment", "--name", "Test Experiment"])
    assert result.exit_code == 0
    assert "EXP001" in result.output
    experiment_file = tmp_path / "workspace" / "experiments" / "EXP001.yaml"
    assert experiment_file.exists()

    result = runner.invoke(
        app,
        [
            "add-query",
            "EXP001",
            "--text",
            "Create a cube.",
            "--model",
            "google/gemini-3-flash-preview",
        ],
    )
    assert result.exit_code == 0
    assert "Q001" in result.output
    experiment_yaml = experiment_file.read_text()
    assert 'text: "Create a cube."' in experiment_yaml
    assert 'model: "google/gemini-3-flash-preview"' in experiment_yaml

    text_file = tmp_path / "query.txt"
    text_file.write_text("Create a bracket from this file.\nAdd two mounting holes.")
    result = runner.invoke(
        app,
        [
            "add-query",
            "EXP001",
            "--text-file",
            str(text_file),
            "--model",
            "google/gemini-3-flash-preview",
        ],
    )
    assert result.exit_code == 0
    assert "Q002" in result.output
    experiment = load_experiment("EXP001")
    assert experiment["queries"][1]["text"] == (
        "Create a bracket from this file.\nAdd two mounting holes."
    )

    result = runner.invoke(app, ["list-queries", "EXP001"])
    assert result.exit_code == 0
    assert "Create a cube." in result.output
    assert "Create a bracket from this file." in result.output
