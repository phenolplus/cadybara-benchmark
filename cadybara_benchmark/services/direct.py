from __future__ import annotations

import re
from typing import Any

from cadybara_benchmark.api_client import CadybaraApiClient
from cadybara_benchmark.config import REPO_ROOT, Settings, get_settings
from cadybara_benchmark.json_utils import dumps_json
from cadybara_benchmark.time import utc_now


def submit_query(
    text: str,
    parameters: dict[str, Any] | None = None,
    client: CadybaraApiClient | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    settings.require_api_key()
    parameters = parameters or {}
    full_parameters = {
        "response_mode": parameters.get("response_mode", settings.default_response_mode),
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
    output_dir.mkdir(parents=True, exist_ok=True)

    stl_path = output_dir / "model.stl"
    response_path = output_dir / "response.json"
    metadata_path = output_dir / "metadata.json"
    stl_path.write_bytes(result.stl_bytes)
    response_path.write_text(dumps_json(result.raw_response))

    generated_code_path = None
    if result.generated_code:
        generated_code_path = output_dir / "generated_code.py"
        generated_code_path.write_text(result.generated_code)

    metadata = {
        "submission_id": submission_id,
        "submitted_at": utc_now(),
        "query": text,
        "parameters": full_parameters,
        "response_metadata": result.response_metadata,
        "stl_path": _stored_path(stl_path),
        "response_path": _stored_path(response_path),
        "generated_code_path": _stored_path(generated_code_path) if generated_code_path else None,
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
