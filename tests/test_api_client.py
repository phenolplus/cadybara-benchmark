from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from cadybara_benchmark.api_client import CadybaraApiClient, CadybaraApiError


def test_generate_json_stl(settings):
    stl_bytes = b"solid api-stl\nendsolid api-stl\n"
    payload = {
        "generated_code": "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)",
        "export_format": "stl",
        "model_base64": base64.b64encode(stl_bytes).decode("ascii"),
        "validation": {"valid": True},
        "response_mode": "json",
    }
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload

    with patch("cadybara_benchmark.api_client.requests.post", return_value=response):
        result = CadybaraApiClient(settings).generate(
            "make a cube",
            {"export_format": "stl", "response_mode": "json"},
        )

    assert result.export_format == "stl"
    assert result.model_bytes == stl_bytes
    assert result.generated_code == payload["generated_code"]


def test_generate_json_code(settings):
    payload = {
        "generated_code": "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)",
        "export_format": "code",
        "validation": {"valid": True},
        "response_mode": "json",
    }
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload

    with patch("cadybara_benchmark.api_client.requests.post", return_value=response):
        result = CadybaraApiClient(settings).generate(
            "make a cube",
            {"export_format": "code", "response_mode": "json"},
        )

    assert result.export_format == "code"
    assert result.model_bytes is None
    assert result.generated_code == payload["generated_code"]


def test_generate_json_step(settings):
    step_bytes = b"STEP payload"
    payload = {
        "generated_code": "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)",
        "export_format": "step",
        "model_base64": base64.b64encode(step_bytes).decode("ascii"),
        "validation": {"valid": True},
        "response_mode": "json",
    }
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload

    with patch("cadybara_benchmark.api_client.requests.post", return_value=response):
        result = CadybaraApiClient(settings).generate(
            "make a cube",
            {"export_format": "step", "response_mode": "json"},
        )

    assert result.export_format == "step"
    assert result.model_bytes == step_bytes


def test_generate_sse_result(settings):
    stl_bytes = b"solid sse-stl\nendsolid sse-stl\n"
    result_event = {
        "type": "result",
        "generated_code": "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)",
        "export_format": "stl",
        "model_base64": base64.b64encode(stl_bytes).decode("ascii"),
        "validation": {"valid": True},
        "response_mode": "sse",
    }
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = [
        'data: {"type": "text", "content": "working..."}',
        f"data: {json.dumps(result_event)}",
    ]

    with patch("cadybara_benchmark.api_client.requests.post", return_value=response):
        result = CadybaraApiClient(settings).generate(
            "make a cube",
            {"export_format": "stl", "response_mode": "sse"},
        )

    assert result.export_format == "stl"
    assert result.model_bytes == stl_bytes
    assert result.response_metadata["response_mode"] == "sse"


def test_generate_sse_error(settings):
    error_event = {
        "type": "error",
        "status_code": 400,
        "code": "VALIDATION_FAILED",
        "error": "Model did not pass validation.",
    }
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = [f"data: {json.dumps(error_event)}"]

    with patch("cadybara_benchmark.api_client.requests.post", return_value=response):
        with pytest.raises(CadybaraApiError) as exc_info:
            CadybaraApiClient(settings).generate(
                "make a cube",
                {"response_mode": "sse"},
            )

    assert exc_info.value.payload["code"] == "VALIDATION_FAILED"
