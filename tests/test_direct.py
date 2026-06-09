from __future__ import annotations

from tests.conftest import BOX_CODE, mock_generate_result
from cadybara_benchmark.services.direct import submit_query


class FakeClient:
    parameters = None

    def generate(self, prompt, parameters):
        self.parameters = parameters
        return mock_generate_result(export_format=parameters.get("export_format", "code"))


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
    assert client.parameters["export_format"] == "code"
    assert result["parameters"]["model"] == "google/gemini-3-flash-preview"
    assert (settings.workspace_dir / "generated" / "direct").exists()
    assert result["stl_path"].endswith("model.stl")
    assert result["response_path"].endswith("response.json")
    assert result["metadata_path"].endswith("metadata.json")
