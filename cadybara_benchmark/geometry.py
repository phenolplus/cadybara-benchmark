from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cadquery as cq
from cadquery import exporters

from cadybara_benchmark.api_client import GenerateResult
from cadybara_benchmark.json_utils import dumps_json


@dataclass(frozen=True)
class ResolvedArtifacts:
    stl_bytes: bytes
    step_bytes: bytes | None = None


def render_code_to_stl(
    code: str,
    *,
    linear_deflection: float,
    angular_deflection: float,
) -> bytes:
    workplane = _execute_generated_code(code)
    return _export_to_stl_bytes(workplane, linear_deflection, angular_deflection)


def render_code_to_step(code: str) -> bytes:
    workplane = _execute_generated_code(code)
    return _export_to_step_bytes(workplane)


def render_step_to_stl(
    step_bytes: bytes,
    *,
    linear_deflection: float,
    angular_deflection: float,
) -> bytes:
    step_path = _write_temp_file(step_bytes, suffix=".step")
    try:
        workplane = cq.importers.importStep(str(step_path))
        return _export_to_stl_bytes(workplane, linear_deflection, angular_deflection)
    finally:
        step_path.unlink(missing_ok=True)


def resolve_query_artifacts(
    result: GenerateResult,
    *,
    linear_deflection: float,
    angular_deflection: float,
) -> ResolvedArtifacts:
    export_format = result.export_format
    if export_format == "stl":
        if not result.model_bytes:
            raise ValueError("STL export did not include model bytes.")
        return ResolvedArtifacts(stl_bytes=result.model_bytes)

    if export_format == "step":
        if not result.model_bytes:
            raise ValueError("STEP export did not include model bytes.")
        stl_bytes = render_step_to_stl(
            result.model_bytes,
            linear_deflection=linear_deflection,
            angular_deflection=angular_deflection,
        )
        return ResolvedArtifacts(stl_bytes=stl_bytes, step_bytes=result.model_bytes)

    if export_format == "code":
        if not result.generated_code:
            raise ValueError("Code export did not include generated_code.")
        stl_bytes = render_code_to_stl(
            result.generated_code,
            linear_deflection=linear_deflection,
            angular_deflection=angular_deflection,
        )
        return ResolvedArtifacts(stl_bytes=stl_bytes)

    raise ValueError(f"Unsupported export_format: {export_format!r}")


def write_generate_artifacts(
    artifact_dir: Path,
    result: GenerateResult,
    *,
    linear_deflection: float,
    angular_deflection: float,
    output_format: str = "stl",
) -> ResolvedArtifacts:
    artifacts = resolve_query_artifacts(
        result,
        linear_deflection=linear_deflection,
        angular_deflection=angular_deflection,
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "model.stl").write_bytes(artifacts.stl_bytes)
    (artifact_dir / "response.json").write_text(dumps_json(result.raw_response))
    if result.generated_code:
        (artifact_dir / "generated_code.py").write_text(result.generated_code)
    if output_format == "step":
        step_bytes = artifacts.step_bytes
        if step_bytes is None and result.generated_code:
            step_bytes = render_code_to_step(result.generated_code)
        if step_bytes:
            (artifact_dir / "model.step").write_bytes(step_bytes)
    return artifacts


def _execute_generated_code(code: str) -> Any:
    namespace: dict[str, Any] = {}
    exec(code, namespace)  # noqa: S102
    result = namespace.get("result")
    if result is None:
        raise ValueError("Generated code did not define `result`.")
    return result


def _export_to_stl_bytes(
    workplane: Any,
    linear_deflection: float,
    angular_deflection: float,
) -> bytes:
    stl_path = _write_temp_file(b"", suffix=".stl")
    try:
        exporters.export(
            workplane,
            str(stl_path),
            exportType=exporters.ExportTypes.STL,
            tolerance=linear_deflection,
            angularTolerance=angular_deflection,
        )
        return stl_path.read_bytes()
    finally:
        stl_path.unlink(missing_ok=True)


def _export_to_step_bytes(workplane: Any) -> bytes:
    step_path = _write_temp_file(b"", suffix=".step")
    try:
        exporters.export(
            workplane,
            str(step_path),
            exportType=exporters.ExportTypes.STEP,
        )
        return step_path.read_bytes()
    finally:
        step_path.unlink(missing_ok=True)


def _write_temp_file(content: bytes, *, suffix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        if content:
            handle.write(content)
    finally:
        handle.close()
    return Path(handle.name)
