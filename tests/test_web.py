from __future__ import annotations

from pathlib import Path

from cadybara_benchmark.api_client import GenerateResult
from cadybara_benchmark.services.experiments import create_experiment
from cadybara_benchmark.services.queries import add_query
from cadybara_benchmark.services.runs import run_experiment
from cadybara_benchmark.web import (
    STATIC_DIR,
    _query_stl_path,
    _run_query,
    stl_viewer,
)


class FakeClient:
    def generate(self, prompt, parameters):
        return GenerateResult(
            stl_bytes=b"solid mock\nendsolid mock\n",
            generated_code="import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)",
            raw_response={"generated_code": "import cadquery as cq", "stl_base64": "..."},
            response_metadata={"latency_ms": 100, "response_mode": "json"},
        )


def _patch_settings(monkeypatch, settings):
    for module in (
        "cadybara_benchmark.web",
        "cadybara_benchmark.run_files",
        "cadybara_benchmark.experiment_files",
        "cadybara_benchmark.services.experiments",
        "cadybara_benchmark.services.runs",
    ):
        monkeypatch.setattr(f"{module}.get_settings", lambda: settings)


def test_stl_viewer_page_and_artifact_resolution(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Viewer Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    page = stl_viewer()
    assert "STL Viewer" in page.body.decode()
    assert (STATIC_DIR / "stl-viewer.html").exists()

    metadata = _run_query("EXP001", "RUN001", "Q001")
    assert metadata["query_id"] == "Q001"
    assert metadata["has_stl"] is True
    assert metadata["text"] == "Create a cube."

    stl_path = _query_stl_path("EXP001", "RUN001", "Q001")
    assert stl_path == Path(settings.workspace_dir / "artifacts" / "EXP001" / "RUN001" / "Q001" / "model.stl")
    assert stl_path.read_bytes().startswith(b"solid mock")


def test_stl_path_rejects_missing_run(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Viewer Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)

    try:
        _query_stl_path("EXP001", "RUN001", "Q001")
    except ValueError as exc:
        assert "Run not found" in str(exc)
    else:
        raise AssertionError("Expected missing run to raise ValueError")
