from __future__ import annotations

from cadybara_benchmark.api_client import GenerateResult
from cadybara_benchmark.services.direct import submit_query


class FakeClient:
    parameters = None

    def generate(self, prompt, parameters):
        self.parameters = parameters
        return GenerateResult(
            stl_bytes=b"solid direct\nendsolid direct\n",
            generated_code="result = None",
            raw_response={
                "generated_code": "result = None",
                "stl_base64": "...",
                "validation": {"valid": True, "confidence": 1.0},
                "response_mode": "json",
            },
            response_metadata={
                "latency_ms": 10,
                "response_mode": "json",
                "validation": {"valid": True, "confidence": 1.0},
            },
        )


def test_submit_query_without_experiment(settings):
    client = FakeClient()
    result = submit_query(
        "Create a cube.",
        parameters={"model": "google/gemini-3-flash-preview"},
        client=client,
        settings=settings,
    )

    assert result["submission_id"].startswith("DIRECT-")
    assert client.parameters["model"] == "google/gemini-3-flash-preview"
    assert result["parameters"]["model"] == "google/gemini-3-flash-preview"
    assert (settings.workspace_dir / "generated" / "direct").exists()
    assert result["stl_path"].endswith("model.stl")
    assert result["response_path"].endswith("response.json")
    assert result["metadata_path"].endswith("metadata.json")
