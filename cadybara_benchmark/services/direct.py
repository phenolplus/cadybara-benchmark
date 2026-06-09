from __future__ import annotations

import re
from typing import Any

from cadybara_benchmark.api_client import CadybaraApiClient
from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings
from cadybara_benchmark.geometry import write_generate_artifacts
from cadybara_benchmark.json_utils import dumps_json
from cadybara_benchmark.time import utc_now


def submit_query(
    text: str,
    parameters: dict[str, Any] | None = None,
    client: CadybaraApiClient | None = None,
    settings: Settings | None = None,
    output_format: str = "stl",
) -> dict[str, Any]:
    settings = settings or get_settings()
    settings.require_api_key()
    parameters = parameters or {}
    if output_format not in {"stl", "step"}:
        raise ValueError("output_format must be 'stl' or 'step'")
    return_format = parameters.get("return_format", settings.default_return_format)
    full_parameters = {
        "response_mode": parameters.get("response_mode", settings.default_response_mode),
        "return_format": return_format,
        "export_format": return_format,
        "output_format": output_format,
        "linear_deflection": parameters.get(
            "linear_deflection", settings.default_linear_deflection
        ),
        "angular_deflection": parameters.get(
            "angular_deflection", settings.default_angular_deflection
        ),
    }
    if parameters.get("model"):
        full_parameters["model"] = parameters["model"]
    client = client or CadybaraApiClient(settings)
    result = client.generate(text, full_parameters)

    submission_id = f"DIRECT-{_path_timestamp(utc_now())}"
    output_dir = settings.workspace_dir / "generated" / "direct" / submission_id
    write_generate_artifacts(
        output_dir,
        result,
        linear_deflection=full_parameters["linear_deflection"],
        angular_deflection=full_parameters["angular_deflection"],
        output_format=output_format,
    )

    stl_path = output_dir / "model.stl"
    response_path = output_dir / "response.json"
    metadata_path = output_dir / "metadata.json"
    generated_code_path = output_dir / "generated_code.py"
    step_path = output_dir / "model.step"

    metadata = {
        "submission_id": submission_id,
        "submitted_at": utc_now(),
        "query": text,
        "parameters": full_parameters,
        "response_metadata": result.response_metadata,
        "stl_path": _stored_path(stl_path),
        "response_path": _stored_path(response_path),
        "generated_code_path": _stored_path(generated_code_path)
        if generated_code_path.exists()
        else None,
        "step_path": _stored_path(step_path) if step_path.exists() else None,
    }
    metadata_path.write_text(dumps_json(metadata))
    metadata["metadata_path"] = _stored_path(metadata_path)
    return metadata


def _path_timestamp(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "", value)


def _stored_path(path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
