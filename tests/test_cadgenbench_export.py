from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import cadybara_benchmark.cadgenbench_export as cadgenbench_export
from cadybara_benchmark.cadgenbench_export import export_cadgenbench_submission
from cadybara_benchmark.experiment_files import save_experiment
from cadybara_benchmark.json_utils import loads_json
from cadybara_benchmark.run_files import run_dir, save_run_summary


def test_export_cadgenbench_writes_submission_package(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))
    monkeypatch.setattr(cadgenbench_export, "render_default_sphere_step", lambda: b"default sphere")
    _write_experiment()
    artifacts = run_dir("EXP001", "RUN001")
    (artifacts / "104").mkdir(parents=True)
    (artifacts / "104" / "model.step").write_text("ISO-10303-21;")
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "completed_with_errors",
            "started_at": "2026-06-09T00:00:00Z",
            "finished_at": "2026-06-09T00:01:00Z",
            "parameters": {},
            "queries": [
                {
                    "query_id": "104",
                    "status": "completed",
                    "artifact_dir": str(artifacts / "104"),
                },
                {
                    "query_id": "201",
                    "status": "failed",
                    "artifact_dir": str(artifacts / "201"),
                },
            ],
            "summary": {"completed": 1, "failed": 1},
        }
    )

    destination = tmp_path / "submission"
    result = export_cadgenbench_submission(
        "EXP001",
        "RUN001",
        destination,
        series="both",
        submitter_name="Ada",
        submission_name="Smoke Run",
        agent_url="https://example.com/agent",
        notes="Generated locally.",
    )

    assert result["count"] == 2
    assert result["with_output_step"] == 2
    meta = loads_json((destination / "meta.json").read_text())
    assert meta["submitter_name"] == "Ada"
    assert meta["submission_name"] == "Smoke Run"
    assert meta["agent_url"] == "https://example.com/agent"
    assert meta["notes"] == "Generated locally."
    assert meta["agree_to_publish"] is True
    assert meta["series"] == "both"
    assert (destination / "104" / "output.step").read_text() == "ISO-10303-21;"
    assert (destination / "201").is_dir()
    assert (destination / "201" / "output.step").read_bytes() == b"default sphere"


def test_export_cadgenbench_filters_series(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))
    monkeypatch.setattr(cadgenbench_export, "render_default_sphere_step", lambda: b"default sphere")
    _write_experiment()
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "completed",
            "started_at": "",
            "finished_at": "",
            "parameters": {},
            "queries": [
                {"query_id": "104", "status": "failed", "artifact_dir": ""},
                {"query_id": "201", "status": "failed", "artifact_dir": ""},
            ],
            "summary": {"completed": 0, "failed": 2},
        }
    )

    destination = tmp_path / "submission"
    result = export_cadgenbench_submission("EXP001", "RUN001", destination, series="200")

    assert result["count"] == 1
    assert result["with_output_step"] == 1
    assert not (destination / "104").exists()
    assert (destination / "201").is_dir()
    assert (destination / "201" / "output.step").read_bytes() == b"default sphere"
    meta = loads_json((destination / "meta.json").read_text())
    assert meta["series"] == "200"


def test_export_cadgenbench_default_submission_metadata(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))
    monkeypatch.setattr(cadgenbench_export, "render_default_sphere_step", lambda: b"default sphere")
    _write_experiment()
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "completed",
            "started_at": "",
            "finished_at": "",
            "parameters": {},
            "queries": [{"query_id": "104", "status": "failed", "artifact_dir": ""}],
            "summary": {"completed": 0, "failed": 1},
        }
    )

    destination = tmp_path / "submission"
    export_cadgenbench_submission("EXP001", "RUN001", destination, series="100")

    meta = loads_json((destination / "meta.json").read_text())
    assert meta["submitter_name"] == "Cadybara"
    assert meta["agent_url"] == "cadybara.com"


def test_export_cadgenbench_render_step_option_uses_generated_code(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))
    monkeypatch.setattr(
        cadgenbench_export,
        "render_code_to_step",
        lambda code: f"rendered from {code}".encode(),
    )
    _write_experiment()
    artifacts = run_dir("EXP001", "RUN001")
    (artifacts / "104").mkdir(parents=True)
    (artifacts / "104" / "model.step").write_text("original step")
    (artifacts / "104" / "generated_code.py").write_text("cadquery code")
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "completed",
            "started_at": "",
            "finished_at": "",
            "parameters": {},
            "queries": [
                {
                    "query_id": "104",
                    "status": "completed",
                    "artifact_dir": str(artifacts / "104"),
                }
            ],
            "summary": {"completed": 1, "failed": 0},
        }
    )

    without_render = tmp_path / "without-render"
    export_cadgenbench_submission("EXP001", "RUN001", without_render, series="100")
    assert (without_render / "104" / "output.step").read_text() == "original step"

    with_render = tmp_path / "with-render"
    result = export_cadgenbench_submission(
        "EXP001",
        "RUN001",
        with_render,
        series="100",
        render_step=True,
    )

    assert result["render_step"] is True
    assert (with_render / "104" / "output.step").read_text() == "rendered from cadquery code"


def test_export_cadgenbench_code_only_sample_uses_default_without_render_step(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))
    monkeypatch.setattr(cadgenbench_export, "render_code_to_step", lambda code: b"rendered step")
    monkeypatch.setattr(cadgenbench_export, "render_default_sphere_step", lambda: b"default sphere")
    _write_experiment()
    artifacts = run_dir("EXP001", "RUN001")
    (artifacts / "104").mkdir(parents=True)
    (artifacts / "104" / "generated_code.py").write_text("cadquery code")
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "completed",
            "started_at": "",
            "finished_at": "",
            "parameters": {},
            "queries": [
                {
                    "query_id": "104",
                    "status": "completed",
                    "artifact_dir": str(artifacts / "104"),
                }
            ],
            "summary": {"completed": 1, "failed": 0},
        }
    )

    without_render = tmp_path / "without-render"
    result = export_cadgenbench_submission("EXP001", "RUN001", without_render, series="100")
    assert result["with_output_step"] == 1
    assert (without_render / "104" / "output.step").read_bytes() == b"default sphere"

    with_render = tmp_path / "with-render"
    result = export_cadgenbench_submission(
        "EXP001",
        "RUN001",
        with_render,
        series="100",
        render_step=True,
    )
    assert result["with_output_step"] == 1
    assert (with_render / "104" / "output.step").read_bytes() == b"rendered step"


def test_export_cadgenbench_render_failure_uses_default_sphere(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))
    monkeypatch.setattr(
        cadgenbench_export,
        "render_code_to_step",
        lambda code: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(cadgenbench_export, "render_default_sphere_step", lambda: b"default sphere")
    _write_experiment()
    artifacts = run_dir("EXP001", "RUN001")
    (artifacts / "104").mkdir(parents=True)
    (artifacts / "104" / "generated_code.py").write_text("bad cadquery code")
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "completed",
            "started_at": "",
            "finished_at": "",
            "parameters": {},
            "queries": [
                {
                    "query_id": "104",
                    "status": "completed",
                    "artifact_dir": str(artifacts / "104"),
                }
            ],
            "summary": {"completed": 1, "failed": 0},
        }
    )

    destination = tmp_path / "submission"
    result = export_cadgenbench_submission(
        "EXP001",
        "RUN001",
        destination,
        series="100",
        render_step=True,
    )

    assert result["with_output_step"] == 1
    assert (destination / "104" / "output.step").read_bytes() == b"default sphere"


def test_export_cadgenbench_copy_fallback_for_200_series(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))
    monkeypatch.setattr(cadgenbench_export, "render_default_sphere_step", lambda: b"default sphere")
    _write_experiment()
    data_dir = tmp_path / "cadgenbench-data"
    (data_dir / "201").mkdir(parents=True)
    (data_dir / "201" / "input.step").write_text("reference 201")
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "completed_with_errors",
            "started_at": "",
            "finished_at": "",
            "parameters": {},
            "queries": [
                {"query_id": "104", "status": "failed", "artifact_dir": ""},
                {"query_id": "201", "status": "failed", "artifact_dir": ""},
            ],
            "summary": {"completed": 0, "failed": 2},
        }
    )

    destination = tmp_path / "submission"
    result = export_cadgenbench_submission(
        "EXP001",
        "RUN001",
        destination,
        series="both",
        copy=True,
        data_dir=data_dir,
    )

    assert result["copy"] is True
    assert result["with_output_step"] == 2
    assert (destination / "104" / "output.step").read_bytes() == b"default sphere"
    assert (destination / "201" / "output.step").read_text() == "reference 201"


def test_export_cadgenbench_copy_does_not_override_run_step(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))
    _write_experiment()
    data_dir = tmp_path / "cadgenbench-data"
    (data_dir / "201").mkdir(parents=True)
    (data_dir / "201" / "input.step").write_text("reference 201")
    artifacts = run_dir("EXP001", "RUN001")
    (artifacts / "201").mkdir(parents=True)
    (artifacts / "201" / "model.step").write_text("run 201")
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "completed",
            "started_at": "",
            "finished_at": "",
            "parameters": {},
            "queries": [
                {
                    "query_id": "201",
                    "status": "completed",
                    "artifact_dir": str(artifacts / "201"),
                }
            ],
            "summary": {"completed": 1, "failed": 0},
        }
    )

    destination = tmp_path / "submission"
    export_cadgenbench_submission(
        "EXP001",
        "RUN001",
        destination,
        series="200",
        copy=True,
        data_dir=data_dir,
    )

    assert (destination / "201" / "output.step").read_text() == "run 201"


def test_export_cadgenbench_can_write_clean_zip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CADYBARA_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("CADYBARA_PUBLISHED_DIR", str(tmp_path / "published"))
    _write_experiment()
    artifacts = run_dir("EXP001", "RUN001")
    (artifacts / "104").mkdir(parents=True)
    (artifacts / "104" / "model.step").write_text("ISO-10303-21;")
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "completed",
            "started_at": "",
            "finished_at": "",
            "parameters": {},
            "queries": [
                {
                    "query_id": "104",
                    "status": "completed",
                    "artifact_dir": str(artifacts / "104"),
                }
            ],
            "summary": {"completed": 1, "failed": 0},
        }
    )
    destination = tmp_path / "submission"
    (destination / "__MACOSX").mkdir(parents=True)
    (destination / ".DS_Store").write_text("finder")
    (destination / "__MACOSX" / "junk").write_text("junk")

    result = export_cadgenbench_submission("EXP001", "RUN001", destination, series="100", zip=True)

    zip_path = Path(result["zip"])
    assert zip_path == destination.with_suffix(".zip")
    assert zip_path.exists()
    with ZipFile(zip_path) as archive:
        names = archive.namelist()
    assert "meta.json" in names
    assert "104/output.step" in names
    assert not any("__MACOSX" in name for name in names)
    assert not any(".DS_Store" in name for name in names)
    assert not any(part.startswith("._") for name in names for part in name.split("/"))
    assert not any(name.startswith("submission/") for name in names)


def _write_experiment() -> None:
    save_experiment(
        {
            "id": "EXP001",
            "name": "CadGenBench Test",
            "description": "",
            "type": "query_comparison",
            "status": "draft",
            "setup": {"model": "google/gemini-3-flash-preview"},
            "created_at": "",
            "updated_at": "",
            "queries": [
                {
                    "id": "104",
                    "text": "Generate sample 104.",
                    "model": "",
                    "category": "cadgenbench-100",
                    "metadata": {"folder_id": 104, "series": "100"},
                },
                {
                    "id": "201",
                    "text": "Generate sample 201.",
                    "model": "",
                    "category": "cadgenbench-200",
                    "metadata": {"folder_id": 201, "series": "200"},
                },
            ],
        }
    )
