from __future__ import annotations

import threading
from pathlib import Path

from tests.conftest import mock_generate_result
from cadybara_benchmark.run_files import get_run
from cadybara_benchmark.services.experiments import create_experiment, get_experiment
from cadybara_benchmark.services.queries import add_query
from cadybara_benchmark.services.runs import resume_run, run_experiment, stop_run
from cadybara_benchmark.web import (
    STATIC_DIR,
    _query_stl_path,
    _run_payload,
    _run_query,
    _sse_message,
    _with_run_stats,
    compare_viewer,
    stl_viewer,
)


class FakeClient:
    def generate(self, prompt, parameters):
        return mock_generate_result()


def _patch_settings(monkeypatch, settings):
    for module in (
        "cadybara_benchmark.web",
        "cadybara_benchmark.run_files",
        "cadybara_benchmark.experiment_files",
        "cadybara_benchmark.services.experiments",
        "cadybara_benchmark.services.runs",
    ):
        monkeypatch.setattr(f"{module}.get_settings", lambda: settings)


def test_stl_viewer_page_and_artifact_resolution(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Viewer Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    page = stl_viewer()
    assert "STL Viewer" in page.body.decode()
    assert (STATIC_DIR / "stl-viewer.html").exists()

    metadata = _run_query("EXP001", "RUN001", "Q001")
    assert metadata["query_id"] == "Q001"
    assert metadata["has_stl"] is True
    assert metadata["text"] == "Create a cube."
    assert metadata["client_latency_ms"] == 100

    stl_path = _query_stl_path("EXP001", "RUN001", "Q001")
    assert stl_path == Path(settings.workspace_dir / "artifacts" / "EXP001" / "RUN001" / "Q001" / "model.stl")
    assert len(stl_path.read_bytes()) > 0


def test_stl_path_rejects_missing_run(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Viewer Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)

    try:
        _query_stl_path("EXP001", "RUN001", "Q001")
    except ValueError as exc:
        assert "Run not found" in str(exc)
    else:
        raise AssertionError("Expected missing run to raise ValueError")


def test_compare_page_and_run_payload(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Compare Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    page = compare_viewer()
    assert "Compare run" in page.body.decode()
    assert (STATIC_DIR / "compare.html").exists()

    payload = _run_payload("EXP001", "RUN001")
    assert payload["id"] == "RUN001"
    assert len(payload["queries"]) == 1
    assert payload["queries"][0]["has_stl"] is True
    assert payload["queries"][0]["text"] == "Create a cube."
    assert payload["queries"][0]["metrics"] == {
        "credit_use": 100,
        "latency": 1.25,
        "steps": 4,
        "tool_calls": 9,
    }
    assert payload["queries"][0]["client_latency_ms"] == 100
    assert payload["average_client_latency_ms"] == 100


def test_with_run_stats_includes_client_latency(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Latency Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    run = _with_run_stats(get_run("EXP001", "RUN001", settings))
    assert run["average_client_latency_ms"] == 100
    assert run["queries"][0]["client_latency_ms"] == 100


def test_compare_renders_client_latency():
    script = (STATIC_DIR / "compare.js").read_text()

    assert "${formatClientLatencyBlock(query)}" in script
    assert '<div class="label">Client latency</div>' in script


def test_app_renders_client_latency():
    script = (STATIC_DIR / "app.js").read_text()

    assert "Avg client latency" in script
    assert "client latency" in script
    assert "getClientLatencyMs" in script


def test_app_optimistically_renders_started_run():
    script = (STATIC_DIR / "app.js").read_text()

    assert "runExperimentWithProgress" in script
    assert "addOptimisticRun(experimentId);" in script
    assert "handleRunProgressEvent" in script
    assert "function nextOptimisticRunId" in script
    assert 'status: "pending"' in script
    assert 'showAlert("Run started.", "info");' in script


def test_run_experiment_emits_progress_events(settings):
    create_experiment("Stream Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)

    events: list[tuple[str, dict]] = []
    run_experiment(
        "EXP001",
        client=FakeClient(),
        settings=settings,
        on_event=lambda event, payload: events.append((event, payload)),
    )

    event_names = [event for event, _payload in events]
    assert event_names[0] == "run_started"
    assert "started" in event_names
    assert "completed" in event_names
    assert events[0][1]["run_id"] == "RUN001"


def test_sse_message_format():
    message = _sse_message("started", {"run_id": "RUN001", "query_id": "Q001"})
    assert message.startswith("data: ")
    assert message.endswith("\n\n")
    assert '"event": "started"' in message


def test_app_supports_run_concurrency():
    script = (STATIC_DIR / "app.js").read_text()

    assert 'id="runConcurrency"' in script
    assert "function parseRunConcurrency" in script
    assert "JSON.stringify({ concurrency })" in script


def test_compare_renders_metrics_list():
    script = (STATIC_DIR / "compare.js").read_text()

    assert "${formatMetricsBlock(query.metrics)}" in script
    assert '<div class="label">Metrics</div>' in script
    assert 'Object.entries(metrics).map(([key, value])' in script


def test_compare_supports_block_reorder_and_minimize():
    script = (STATIC_DIR / "compare.js").read_text()

    assert "compare-block-header" in script
    assert "compare-block-drag" in script
    assert "compare-block-minimize" in script
    assert "setupDragReorder" in script
    assert "setupMinimize" in script
    assert "is-minimized" in script
    assert "compare-minimized-stack" in script


def test_compare_disables_camera_controls_for_dnf_viewports():
    script = (STATIC_DIR / "compare.js").read_text()
    css = (STATIC_DIR / "compare.css").read_text()

    assert "function isDnfQuery" in script
    assert "controls.enabled = !isDnf" in script
    assert "if (viewport.isDnf) return" in script
    assert "isDnf" in script
    assert ".compare-viewport.is-empty .compare-viewport-stage" in css
    assert "pointer-events: none" in css


def test_app_supports_image_prompt_ui():
    script = (STATIC_DIR / "app.js").read_text()

    assert 'name="image"' in script
    assert "readImagePayload" in script
    assert "formatQueryImages" in script
    assert "Reference image" in script


def test_compare_supports_image_prompt_ui():
    script = (STATIC_DIR / "compare.js").read_text()

    assert "formatQueryImagesBlock" in script
    assert "Reference image" in script


class BlockingClient:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def generate(self, prompt, parameters):
        self.started.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("Timed out waiting for release signal.")
        return mock_generate_result()


def test_stop_run_cancels_pending_queries(settings):
    create_experiment("Stop Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    add_query("EXP001", "Create a sphere.", settings=settings)

    client = BlockingClient()

    def execute() -> None:
        run_experiment("EXP001", client=client, settings=settings, concurrency=1)

    thread = threading.Thread(target=execute)
    thread.start()
    assert client.started.wait(timeout=5)

    stopped = stop_run("EXP001", "RUN001", settings=settings)
    assert stopped["status"] == "stopped"

    client.release.set()
    thread.join(timeout=5)

    run = get_run("EXP001", "RUN001", settings)
    assert run["status"] == "stopped"
    statuses = [query["status"] for query in run["queries"]]
    assert statuses.count("cancelled") >= 1
    assert get_experiment("EXP001", settings)["status"] == "stopped"


def test_stop_run_rejects_non_running_run(settings):
    create_experiment("Stop Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    try:
        stop_run("EXP001", "RUN001", settings=settings)
    except ValueError as exc:
        assert "not running" in str(exc)
    else:
        raise AssertionError("Expected stop_run to reject a completed run")


def test_app_renders_stop_button_for_running_runs():
    script = (STATIC_DIR / "app.js").read_text()

    assert 'run.status === "running"' in script
    assert "function stopRun" in script
    assert "/stop" in script
    assert "btn-outline-danger" in script


def test_resume_run_completes_cancelled_queries(settings):
    create_experiment("Resume Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    add_query("EXP001", "Create a sphere.", settings=settings)

    client = BlockingClient()

    def execute() -> None:
        run_experiment("EXP001", client=client, settings=settings, concurrency=1)

    thread = threading.Thread(target=execute)
    thread.start()
    assert client.started.wait(timeout=5)

    stop_run("EXP001", "RUN001", settings=settings)
    client.release.set()
    thread.join(timeout=5)

    stopped_run = get_run("EXP001", "RUN001", settings)
    assert stopped_run["status"] == "stopped"
    assert any(query["status"] == "cancelled" for query in stopped_run["queries"])

    result = resume_run("EXP001", "RUN001", client=FakeClient(), settings=settings)
    assert result["resumed"] is True
    assert result["stopped"] is False

    run = get_run("EXP001", "RUN001", settings)
    assert run["status"] == "completed"
    assert all(query["status"] == "completed" for query in run["queries"])
    assert get_experiment("EXP001", settings)["status"] == "completed"


def test_resume_run_rejects_non_stopped_run(settings):
    create_experiment("Resume Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    try:
        resume_run("EXP001", "RUN001", client=FakeClient(), settings=settings)
    except ValueError as exc:
        assert "not stopped" in str(exc)
    else:
        raise AssertionError("Expected resume_run to reject a completed run")


def test_resume_run_rejects_when_no_cancelled_queries(settings):
    create_experiment("Resume Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    run = get_run("EXP001", "RUN001", settings)
    run["status"] = "stopped"
    from cadybara_benchmark.run_files import save_run_summary

    save_run_summary(run, settings)

    try:
        resume_run("EXP001", "RUN001", client=FakeClient(), settings=settings)
    except ValueError as exc:
        assert "no cancelled queries" in str(exc)
    else:
        raise AssertionError("Expected resume_run to reject a run with no cancelled queries")


def test_app_renders_resume_button_for_stopped_runs():
    script = (STATIC_DIR / "app.js").read_text()

    assert "function canResumeRun" in script
    assert "function resumeRun" in script
    assert "/resume" in script
    assert 'query.status === "cancelled"' in script
    assert "btn-outline-success" in script


def test_app_route_resets_modal_backdrop():
    script = (STATIC_DIR / "app.js").read_text()

    route_start = script.index("async function route()")
    route_body = script[route_start : script.index("async function renderExperiments()")]
    assert "resetModalState();" in route_body

    reset_start = script.index("function resetModalState()")
    reset_body = script[reset_start : script.index("function escapeHtml")]
    assert '".modal-backdrop"' in reset_body
    assert '"modal-open"' in reset_body
