from __future__ import annotations

import pytest

from cadybara_benchmark.api_client import GenerateResult
from cadybara_benchmark.config import Settings


BOX_CODE = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)"
MOCK_STL_BYTES = b"solid mock\nendsolid mock\n"


def mock_generate_result(
    *,
    export_format: str = "code",
    generated_code: str | None = None,
    model_bytes: bytes | None = None,
    raw_response: dict | None = None,
    response_metadata: dict | None = None,
) -> GenerateResult:
    if export_format == "code":
        generated_code = generated_code or BOX_CODE
    elif model_bytes is None:
        model_bytes = MOCK_STL_BYTES

    raw_response = raw_response or {
        "generated_code": generated_code,
        "export_format": export_format,
        "validation": {"valid": True, "confidence": 0.9},
        "response_mode": "json",
        "metrics": {
            "credit_use": 100,
            "latency": 1.25,
            "steps": 4,
            "tool_calls": 9,
        },
    }
    response_metadata = response_metadata or {
        "latency_ms": 100,
        "response_mode": "json",
        "export_format": export_format,
        "validation": {"valid": True, "confidence": 0.9},
    }
    return GenerateResult(
        export_format=export_format,
        raw_response=raw_response,
        response_metadata=response_metadata,
        generated_code=generated_code,
        model_bytes=model_bytes,
    )


@pytest.fixture
def settings(tmp_path):
    workspace = tmp_path / "workspace"
    published = tmp_path / "published"
    test_settings = Settings(
        api_base_url="https://api.cadybara.com",
        api_key="pfk_test",
        workspace_dir=workspace,
        published_dir=published,
        default_response_mode="json",
        default_return_format="code",
        default_linear_deflection=0.1,
        default_angular_deflection=0.1,
        request_timeout_seconds=180,
    )
    return test_settings
