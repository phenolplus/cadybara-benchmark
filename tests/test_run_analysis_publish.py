from __future__ import annotations

from cadybara_benchmark.api_client import GenerateResult
from cadybara_benchmark.publishing import publish_experiment
from cadybara_benchmark.run_files import get_run, list_runs, next_run_id, summary_path
from cadybara_benchmark.services.analysis import analyze_experiment
from cadybara_benchmark.services.experiments import create_experiment
from cadybara_benchmark.services.queries import add_query
from cadybara_benchmark.services.runs import list_results_for_experiment, run_experiment


class FakeClient:
    parameters = None
    calls = None

    def generate(self, prompt, parameters):
        self.parameters = parameters
        if self.calls is None:
            self.calls = []
        self.calls.append({"prompt": prompt, "parameters": parameters})
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
                "metrics": {
                    "credit_use": 100,
                    "latency": 1.25,
                    "steps": 4,
                    "tool_calls": 9,
                },
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
    add_query("EXP001", "Create a cube.", "mechanical", sublabel="cube-default", settings=settings)
    add_query(
        "EXP001",
        "Create a sphere.",
        "mechanical",
        model="google/gemini-3-flash-preview",
        sublabel="sphere-gemini",
        settings=settings,
    )

    client = FakeClient()
    summary = run_experiment(
        "EXP001",
        model="google/gemini-3-flash-preview",
        client=client,
        settings=settings,
    )

    assert summary["completed"] == 2
    assert summary["failed"] == 0
    assert summary["run_id"] == "RUN001"
    assert client.calls[0]["parameters"]["model"] == "google/gemini-3-flash-preview"
    assert client.calls[1]["parameters"]["model"] == "google/gemini-3-flash-preview"

    runs = list_runs("EXP001", settings)
    assert len(runs) == 1
    run = runs[0]
    assert run["status"] == "completed"
    assert [query["model"] for query in run["queries"]] == [
        "google/gemini-3-flash-preview",
        "google/gemini-3-flash-preview",
    ]
    assert [query["sublabel"] for query in run["queries"]] == [
        "cube-default",
        "sphere-gemini",
    ]
    assert [query["text"] for query in run["queries"]] == [
        "Create a cube.",
        "Create a sphere.",
    ]
    assert [query["metrics"] for query in run["queries"]] == [
        {"credit_use": 100, "latency": 1.25, "steps": 4, "tool_calls": 9},
        {"credit_use": 100, "latency": 1.25, "steps": 4, "tool_calls": 9},
    ]

    result = list_results_for_experiment("EXP001", settings)[0]
    assert result["metrics"] == {
        "credit_use": 100,
        "latency": 1.25,
        "steps": 4,
        "tool_calls": 9,
    }
    assert result["stl_paths"] == [
        str(settings.workspace_dir / "artifacts" / "EXP001" / "RUN001" / "Q001" / "model.stl")
    ]
    assert summary_path("EXP001", "RUN001", settings).exists()

    report = analyze_experiment("EXP001", settings)
    assert report["summary"]["average_overall_score"] == 0.95
    assert report["summary"]["run_count"] == 1
    assert report["summary"]["query_result_count"] == 2
    assert (settings.workspace_dir / "reports" / "EXP001.json").exists()

    run = get_run("EXP001", "RUN001", settings)
    assert all(query["score"] == 0.95 for query in run["queries"])

    published = publish_experiment("EXP001", settings=settings)
    assert published["count"] == 1
    assert (settings.published_dir / "runs" / "RUN001.json").exists()
    assert (settings.published_dir / "runs" / "RUN001" / "Q001" / "model.stl").exists()
    assert (settings.published_dir / "runs" / "RUN001" / "Q002" / "model.stl").exists()


def test_run_uses_query_model_over_experiment_default(settings):
    create_experiment(
        "Model Override",
        setup={
            "model": "default-model",
            "response_mode": "json",
            "linear_deflection": 0.1,
            "angular_deflection": 0.1,
        },
        settings=settings,
    )
    add_query("EXP001", "Create a cube.", sublabel="cube", settings=settings)
    add_query("EXP001", "Create a sphere.", model="query-model", sublabel="sphere", settings=settings)

    client = FakeClient()
    run_experiment("EXP001", client=client, settings=settings)

    assert [call["parameters"]["model"] for call in client.calls] == [
        "default-model",
        "query-model",
    ]
    run = list_runs("EXP001", settings)[0]
    assert [query["model"] for query in run["queries"]] == [
        "default-model",
        "query-model",
    ]
    assert [query["sublabel"] for query in run["queries"]] == [
        "cube",
        "sphere",
    ]


def test_next_run_id_increments(settings):
    assert next_run_id("EXP001", settings) == "RUN001"
    summary_path("EXP001", "RUN001", settings).parent.mkdir(parents=True)
    summary_path("EXP001", "RUN001", settings).write_text("{}")
    assert next_run_id("EXP001", settings) == "RUN002"
