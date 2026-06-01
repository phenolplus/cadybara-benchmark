from __future__ import annotations

from typer.testing import CliRunner

from cadybara_benchmark.cli import app


runner = CliRunner()


def test_cli_create_and_add_query(tmp_path, monkeypatch):
    monkeypatch.setenv("CADYBARA_DB_PATH", str(tmp_path / "workspace" / "research.db"))
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))

    result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["create-experiment", "--name", "Test Experiment"])
    assert result.exit_code == 0
    assert "EXP001" in result.output

    result = runner.invoke(app, ["add-query", "EXP001", "--text", "Create a cube."])
    assert result.exit_code == 0
    assert "Q001" in result.output

    result = runner.invoke(app, ["list-queries", "EXP001"])
    assert result.exit_code == 0
    assert "Create a cube." in result.output
