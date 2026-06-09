from __future__ import annotations

import tempfile
from pathlib import Path

import cadquery as cq
from cadquery import exporters

from cadybara_benchmark.api_client import GenerateResult
from cadybara_benchmark.geometry import (
    render_code_to_step,
    render_code_to_stl,
    render_step_to_stl,
    resolve_query_artifacts,
    write_generate_artifacts,
)


BOX_CODE = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)"


def test_render_code_to_stl():
    stl_bytes = render_code_to_stl(
        BOX_CODE,
        linear_deflection=0.1,
        angular_deflection=0.1,
    )

    assert stl_bytes
    assert len(stl_bytes) > 0


def test_render_code_to_step():
    step_bytes = render_code_to_step(BOX_CODE)

    assert step_bytes
    assert len(step_bytes) > 0


def test_write_generate_artifacts_output_format_step(tmp_path):
    result = GenerateResult(
        export_format="code",
        raw_response={"export_format": "code", "generated_code": BOX_CODE},
        response_metadata={},
        generated_code=BOX_CODE,
    )

    write_generate_artifacts(
        tmp_path,
        result,
        linear_deflection=0.1,
        angular_deflection=0.1,
        output_format="step",
    )

    assert (tmp_path / "model.stl").stat().st_size > 0
    assert (tmp_path / "model.step").stat().st_size > 0


def test_write_generate_artifacts_output_format_stl_skips_step(tmp_path):
    result = GenerateResult(
        export_format="code",
        raw_response={"export_format": "code", "generated_code": BOX_CODE},
        response_metadata={},
        generated_code=BOX_CODE,
    )

    write_generate_artifacts(
        tmp_path,
        result,
        linear_deflection=0.1,
        angular_deflection=0.1,
        output_format="stl",
    )

    assert (tmp_path / "model.stl").exists()
    assert not (tmp_path / "model.step").exists()


def test_render_step_to_stl():
    step_bytes = _export_step_bytes()
    stl_bytes = render_step_to_stl(
        step_bytes,
        linear_deflection=0.1,
        angular_deflection=0.1,
    )

    assert stl_bytes
    assert len(stl_bytes) > 0


def test_resolve_query_artifacts_stl():
    result = GenerateResult(
        export_format="stl",
        raw_response={"export_format": "stl"},
        response_metadata={},
        model_bytes=b"solid test\nendsolid test\n",
    )

    artifacts = resolve_query_artifacts(
        result,
        linear_deflection=0.1,
        angular_deflection=0.1,
    )

    assert artifacts.stl_bytes == b"solid test\nendsolid test\n"
    assert artifacts.step_bytes is None


def test_resolve_query_artifacts_code():
    result = GenerateResult(
        export_format="code",
        raw_response={"export_format": "code", "generated_code": BOX_CODE},
        response_metadata={},
        generated_code=BOX_CODE,
    )

    artifacts = resolve_query_artifacts(
        result,
        linear_deflection=0.1,
        angular_deflection=0.1,
    )

    assert artifacts.stl_bytes
    assert artifacts.step_bytes is None


def test_resolve_query_artifacts_step():
    step_bytes = _export_step_bytes()
    result = GenerateResult(
        export_format="step",
        raw_response={"export_format": "step"},
        response_metadata={},
        model_bytes=step_bytes,
    )

    artifacts = resolve_query_artifacts(
        result,
        linear_deflection=0.1,
        angular_deflection=0.1,
    )

    assert artifacts.step_bytes == step_bytes
    assert artifacts.stl_bytes


def _export_step_bytes() -> bytes:
    workplane = cq.Workplane("XY").box(2, 2, 2)
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as handle:
        step_path = Path(handle.name)
    try:
        exporters.export(workplane, str(step_path), exportType=exporters.ExportTypes.STEP)
        return step_path.read_bytes()
    finally:
        step_path.unlink(missing_ok=True)
