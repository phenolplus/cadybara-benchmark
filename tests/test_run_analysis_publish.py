from __future__ import annotations

import json
import threading
import time

from tests.conftest import BOX_CODE, MOCK_STL_BYTES, mock_generate_result
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
        return mock_generate_result()


def test_run_analyze_and_publish(settings):
    create_experiment("Bracket Query Comparison", settings=settings)
    add_query("EXP001", "Create a cube.", "mechanical", settings=settings)
    add_query(
        "EXP001",
        "Create a sphere.",
        "mechanical",
        model="google/gemini-3-flash-preview",
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

    published_payload = json.loads((settings.published_dir / "runs" / "RUN001.json").read_text())
    assert all(query["client_latency_ms"] == 100 for query in published_payload["queries"])


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
    add_query("EXP001", "Create a cube.", settings=settings)
    add_query("EXP001", "Create a sphere.", model="query-model", settings=settings)

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


class ConcurrentTrackingClient:
    def __init__(self, delay_seconds: float = 0.05):
        self.delay_seconds = delay_seconds
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.calls: list[dict] = []

    def generate(self, prompt, parameters):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.calls.append({"prompt": prompt, "parameters": parameters})
        try:
            time.sleep(self.delay_seconds)
            return mock_generate_result()
        finally:
            with self.lock:
                self.active -= 1


def test_run_experiment_respects_concurrency(settings):
    create_experiment("Concurrent Run", settings=settings)
    for index in range(4):
        add_query("EXP001", f"Create part {index}.", settings=settings)

    client = ConcurrentTrackingClient()
    summary = run_experiment("EXP001", client=client, settings=settings, concurrency=2)

    assert summary["completed"] == 4
    assert summary["failed"] == 0
    assert client.max_active == 2
    assert len(client.calls) == 4

    run = list_runs("EXP001", settings)[0]
    assert run["parameters"]["concurrency"] == 2
    assert [query["status"] for query in run["queries"]] == ["completed"] * 4


def test_run_experiment_defaults_to_sequential_concurrency(settings):
    create_experiment("Sequential Run", settings=settings)
    for index in range(3):
        add_query("EXP001", f"Create part {index}.", settings=settings)

    client = ConcurrentTrackingClient()
    run_experiment("EXP001", client=client, settings=settings)

    assert client.max_active == 1


def test_next_run_id_increments(settings):
    assert next_run_id("EXP001", settings) == "RUN001"
    summary_path("EXP001", "RUN001", settings).parent.mkdir(parents=True)
    summary_path("EXP001", "RUN001", settings).write_text("{}")
    assert next_run_id("EXP001", settings) == "RUN002"


class ReturnFormatClient:
    def __init__(self, export_format: str):
        self.export_format = export_format
        self.calls: list[dict] = []

    def generate(self, prompt, parameters):
        self.calls.append({"prompt": prompt, "parameters": parameters})
        if self.export_format == "step":
            return mock_generate_result(
                export_format="step",
                generated_code=BOX_CODE,
                model_bytes=_step_bytes(),
            )
        if self.export_format == "code":
            return mock_generate_result(export_format="code", generated_code=BOX_CODE)
        return mock_generate_result(export_format="stl", model_bytes=MOCK_STL_BYTES)


def test_run_experiment_uses_return_format_code(settings):
    create_experiment(
        "Code Return Format",
        setup={
            "model": "default",
            "response_mode": "json",
            "return_format": "code",
            "linear_deflection": 0.1,
            "angular_deflection": 0.1,
        },
        settings=settings,
    )
    add_query("EXP001", "Create a cube.", settings=settings)

    client = ReturnFormatClient("code")
    summary = run_experiment("EXP001", client=client, settings=settings)

    assert summary["completed"] == 1
    assert client.calls[0]["parameters"]["export_format"] == "code"
    artifact_dir = settings.workspace_dir / "artifacts" / "EXP001" / "RUN001" / "Q001"
    assert (artifact_dir / "model.stl").exists()
    assert (artifact_dir / "generated_code.py").exists()
    assert not (artifact_dir / "model.step").exists()


def test_run_experiment_uses_return_format_step(settings):
    create_experiment(
        "Step Return Format",
        setup={
            "model": "default",
            "response_mode": "json",
            "return_format": "step",
            "linear_deflection": 0.1,
            "angular_deflection": 0.1,
        },
        settings=settings,
    )
    add_query("EXP001", "Create a cube.", settings=settings)

    client = ReturnFormatClient("step")
    summary = run_experiment(
        "EXP001", client=client, settings=settings, output_format="step"
    )

    assert summary["completed"] == 1
    assert client.calls[0]["parameters"]["export_format"] == "step"
    artifact_dir = settings.workspace_dir / "artifacts" / "EXP001" / "RUN001" / "Q001"
    assert (artifact_dir / "model.step").exists()
    assert (artifact_dir / "model.stl").exists()


def test_run_experiment_output_format_stl_skips_local_step(settings):
    create_experiment(
        "Step API Only",
        setup={
            "model": "default",
            "response_mode": "json",
            "return_format": "step",
            "linear_deflection": 0.1,
            "angular_deflection": 0.1,
        },
        settings=settings,
    )
    add_query("EXP001", "Create a cube.", settings=settings)

    client = ReturnFormatClient("step")
    run_experiment("EXP001", client=client, settings=settings, output_format="stl")

    artifact_dir = settings.workspace_dir / "artifacts" / "EXP001" / "RUN001" / "Q001"
    assert (artifact_dir / "model.stl").exists()
    assert not (artifact_dir / "model.step").exists()


def test_run_experiment_output_format_step_renders_from_code(settings):
    create_experiment(
        "Code API With Step Output",
        setup={
            "model": "default",
            "response_mode": "json",
            "return_format": "code",
            "linear_deflection": 0.1,
            "angular_deflection": 0.1,
        },
        settings=settings,
    )
    add_query("EXP001", "Create a cube.", settings=settings)

    client = ReturnFormatClient("code")
    run_experiment("EXP001", client=client, settings=settings, output_format="step")

    artifact_dir = settings.workspace_dir / "artifacts" / "EXP001" / "RUN001" / "Q001"
    assert (artifact_dir / "model.stl").exists()
    assert (artifact_dir / "model.step").exists()


def _step_bytes() -> bytes:
    import tempfile
    from pathlib import Path

    import cadquery as cq
    from cadquery import exporters

    workplane = cq.Workplane("XY").box(2, 2, 2)
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as handle:
        step_path = Path(handle.name)
    try:
        exporters.export(workplane, str(step_path), exportType=exporters.ExportTypes.STEP)
        return step_path.read_bytes()
    finally:
        step_path.unlink(missing_ok=True)
