from __future__ import annotations

from cadybara_benchmark.api_client import GenerateResult
from cadybara_benchmark.publishing import publish_experiment
from cadybara_benchmark.services.analysis import analyze_experiment
from cadybara_benchmark.services.experiments import create_experiment
from cadybara_benchmark.services.queries import add_query
from cadybara_benchmark.services.runs import list_results_for_experiment, list_runs, run_experiment


class FakeClient:
    parameters = None

    def generate(self, prompt, parameters):
        self.parameters = parameters
        return GenerateResult(
            stl_bytes=b"solid mock\nendsolid mock\n",
            generated_code="import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)",
            raw_response={
                "generated_code": "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)",
                "stl_base64": "...",
                "validation": {
                    "valid": True,
                    "confidence": 0.9,
                    "issues": [],
                    "brief_reason": "Mock validation passed.",
                    "attempt_count": 1,
                    "max_attempts": 3,
                },
                "response_mode": "json",
            },
            response_metadata={
                "latency_ms": 100,
                "response_mode": "json",
                "validation": {
                    "valid": True,
                    "confidence": 0.9,
                    "attempt_count": 1,
                    "max_attempts": 3,
                },
            },
        )


def test_run_analyze_and_publish(settings):
    create_experiment("Bracket Query Comparison", settings=settings)
    add_query("EXP001", "Create a cube.", "mechanical", settings=settings)

    client = FakeClient()
    summary = run_experiment(
        "EXP001",
        model="google/gemini-3-flash-preview",
        client=client,
        settings=settings,
    )

    assert summary["completed"] == 1
    assert client.parameters["model"] == "google/gemini-3-flash-preview"
    assert list_runs("EXP001", settings)[0]["status"] == "completed"
    result = list_results_for_experiment("EXP001", settings)[0]
    assert result["stl_paths"] == [str(settings.workspace_dir / "artifacts" / "EXP001" / "RUN001" / "model.stl")]

    report = analyze_experiment("EXP001", settings)
    assert report["summary"]["average_overall_score"] == 0.95
    assert (settings.workspace_dir / "reports" / "EXP001.json").exists()

    published = publish_experiment("EXP001", settings=settings)
    assert published["count"] == 1
    assert (settings.published_dir / "runs" / "RUN001.json").exists()
    assert (settings.published_dir / "runs" / "RUN001" / "model.stl").exists()
