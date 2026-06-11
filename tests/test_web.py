from __future__ import annotations

import threading
from pathlib import Path

from tests.conftest import mock_generate_result
from cadybara_benchmark.run_files import get_run
from cadybara_benchmark.services.experiments import create_experiment, get_experiment
from cadybara_benchmark.services.queries import add_query
from cadybara_benchmark.run_files import save_run_summary
from cadybara_benchmark.services.runs import (
    reconcile_persisted_run_state,
    resume_run,
    retry_run,
    run_experiment,
    stop_run,
)
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
    assert payload["total_client_latency_ms"] == 100
    assert payload["eta_ms"] is None


def test_with_run_stats_includes_run_time(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Latency Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    run = _with_run_stats(get_run("EXP001", "RUN001", settings))
    assert run["total_client_latency_ms"] == 100
    assert run["eta_ms"] is None
    assert run["queries"][0]["client_latency_ms"] == 100


def test_compare_renders_client_latency():
    script = (STATIC_DIR / "compare.js").read_text()

    assert "${formatClientLatencyBlock(query)}" in script
    assert '<div class="label">Client latency</div>' in script


def test_compare_builds_blocks_from_experiment_queries(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("In Progress Compare", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    add_query("EXP001", "Create a sphere.", settings=settings)

    run_summary = {
        "id": "RUN001",
        "experiment_id": "EXP001",
        "status": "running",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "",
        "parameters": {},
        "queries": [
            {
                "query_id": "Q001",
                "text": "Create a cube.",
                "model": "default",
                "images": [],
                "status": "pending",
                "error": {},
                "artifact_dir": "",
                "response_metadata": {},
                "score": None,
                "metrics": {},
            },
            {
                "query_id": "Q002",
                "text": "Create a sphere.",
                "model": "default",
                "images": [],
                "status": "running",
                "error": {},
                "artifact_dir": "",
                "response_metadata": {},
                "score": None,
                "metrics": {},
            },
        ],
        "summary": {"completed": 0, "failed": 0},
    }
    save_run_summary(run_summary, settings)

    payload = _run_payload("EXP001", "RUN001")
    assert len(payload["queries"]) == 2
    assert {query["query_id"] for query in payload["queries"]} == {"Q001", "Q002"}


def test_compare_page_supports_in_progress_runs():
    script = (STATIC_DIR / "compare.js").read_text()

    assert "function buildCompareItems" in script
    assert "function autoMinimizeInProgressBlocks" in script
    assert "function escapeAttr" in script
    assert 'query.status === "pending" || query.status === "running"' in script
    assert "fetchJson(`/api/experiments/${encodeURIComponent(experimentId)}`)" in script


def test_app_renders_run_time():
    script = (STATIC_DIR / "app.js").read_text()

    assert ">Time</th>" in script
    assert "formatRunTime" in script
    assert "getRunEtaMs" in script
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
    assert "data-run-action" in script
    assert 'runActionButton("Stop", "stop"' in script


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


def test_resume_run_rejects_when_no_resumable_queries(settings):
    create_experiment("Resume Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    run = get_run("EXP001", "RUN001", settings)
    run["status"] = "stopped"
    save_run_summary(run, settings)

    try:
        resume_run("EXP001", "RUN001", client=FakeClient(), settings=settings)
    except ValueError as exc:
        assert "no resumable queries" in str(exc)
    else:
        raise AssertionError("Expected resume_run to reject a run with no resumable queries")


def _stopped_run_with_cancelled_query(
    experiment_id: str,
    run_id: str,
    query_id: str,
    text: str,
) -> dict:
    return {
        "id": run_id,
        "experiment_id": experiment_id,
        "status": "stopped",
        "started_at": "2026-06-05T12:00:00Z",
        "finished_at": "2026-06-05T12:05:00Z",
        "parameters": {"output_format": "stl", "concurrency": 1},
        "queries": [
            {
                "query_id": query_id,
                "text": text,
                "model": "default",
                "images": [],
                "status": "cancelled",
                "error": {},
                "artifact_dir": "",
                "response_metadata": {},
                "score": None,
                "metrics": {},
            }
        ],
        "summary": {"completed": 0, "failed": 0},
    }


def test_resume_run_uses_experiment_scoped_run_id(settings):
    create_experiment("Resume Scope A", settings=settings)
    create_experiment("Resume Scope B", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    add_query("EXP002", "Create a sphere.", settings=settings)

    save_run_summary(
        _stopped_run_with_cancelled_query("EXP001", "RUN001", "Q001", "Create a cube."),
        settings,
    )
    save_run_summary(
        _stopped_run_with_cancelled_query("EXP002", "RUN001", "Q001", "Create a sphere."),
        settings,
    )

    result = resume_run("EXP002", "RUN001", client=FakeClient(), settings=settings)
    assert result["resumed"] is True

    exp002_run = get_run("EXP002", "RUN001", settings)
    assert exp002_run["status"] in {"completed", "completed_with_errors"}
    assert exp002_run["queries"][0]["status"] != "cancelled"
    assert exp002_run["queries"][0]["text"] == "Create a sphere."

    exp001_run = get_run("EXP001", "RUN001", settings)
    assert exp001_run["status"] == "stopped"
    assert exp001_run["queries"][0]["status"] == "cancelled"


def test_app_renders_resume_button_for_stopped_runs():
    script = (STATIC_DIR / "app.js").read_text()

    assert "function shouldShowResume" in script
    assert "function resumeRun" in script
    assert "/resume" in script
    assert 'query.status === "cancelled"' in script
    assert 'query.status === "pending"' in script
    assert "run.can_resume" in script
    assert "data-run-action" in script
    assert 'runActionButton("Resume", "resume"' in script
    assert "btn-outline-success" in script
    assert "Resume cancelled queries" in script


def test_app_renders_retry_button_for_failed_runs():
    script = (STATIC_DIR / "app.js").read_text()

    assert "function shouldShowRetry" in script
    assert "function retryRun" in script
    assert "/retry" in script
    assert 'query.status === "failed"' in script
    assert "run.can_retry" in script
    assert 'runActionButton("Retry", "retry"' in script
    assert "btn-outline-warning" in script
    assert script.index('run.status !== "completed_with_errors"') < script.index("run.can_retry")


def test_should_show_retry_hides_while_running():
    script = (STATIC_DIR / "app.js").read_text()
    start = script.index("function shouldShowRetry")
    end = script.index("function runActionButton", start)
    body = script[start:end]

    status_guard = body.index('run.status !== "completed_with_errors"')
    can_retry_check = body.index("run.can_retry")
    assert status_guard < can_retry_check


def test_with_run_stats_exposes_can_resume(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Resume Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "stopped",
            "started_at": "2026-06-05T12:00:00Z",
            "finished_at": "2026-06-05T12:05:00Z",
            "parameters": {},
            "queries": [
                {
                    "query_id": "Q001",
                    "text": "Create a cube.",
                    "model": "default",
                    "images": [],
                    "status": "pending",
                    "error": {},
                    "artifact_dir": "",
                    "response_metadata": {},
                    "score": None,
                    "metrics": {},
                }
            ],
            "summary": {"completed": 0, "failed": 0},
        },
        settings,
    )

    run = _with_run_stats(get_run("EXP001", "RUN001", settings))
    assert run["can_resume"] is True


def test_with_run_stats_exposes_can_retry(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Retry Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    save_run_summary(
        _completed_run_with_failed_query("EXP001", "RUN001", "Q001", "Create a cube."),
        settings,
    )

    run = _with_run_stats(get_run("EXP001", "RUN001", settings))
    assert run["can_retry"] is True


def _completed_run_with_failed_query(
    experiment_id: str,
    run_id: str,
    query_id: str,
    text: str,
    *,
    completed_query_id: str | None = None,
    completed_text: str | None = None,
) -> dict:
    queries = []
    if completed_query_id is not None:
        queries.append(
            {
                "query_id": completed_query_id,
                "text": completed_text or "",
                "model": "default",
                "images": [],
                "status": "completed",
                "error": {},
                "artifact_dir": "",
                "response_metadata": {},
                "score": None,
                "metrics": {},
            }
        )
    queries.append(
        {
            "query_id": query_id,
            "text": text,
            "model": "default",
            "images": [],
            "status": "failed",
            "error": {"message": "API error"},
            "artifact_dir": "",
            "response_metadata": {},
            "score": None,
            "metrics": {},
        }
    )
    completed = sum(1 for query in queries if query["status"] == "completed")
    failed = sum(1 for query in queries if query["status"] == "failed")
    return {
        "id": run_id,
        "experiment_id": experiment_id,
        "status": "completed_with_errors",
        "started_at": "2026-06-05T12:00:00Z",
        "finished_at": "2026-06-05T12:05:00Z",
        "parameters": {
            "response_mode": "json",
            "return_format": "code",
            "export_format": "code",
            "linear_deflection": 0.1,
            "angular_deflection": 0.1,
            "concurrency": 1,
            "output_format": "stl",
        },
        "queries": queries,
        "summary": {"completed": completed, "failed": failed},
    }


def test_retry_run_retries_failed_queries(settings):
    create_experiment("Retry Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    add_query("EXP001", "Create a sphere.", settings=settings)
    save_run_summary(
        _completed_run_with_failed_query(
            "EXP001",
            "RUN001",
            "Q002",
            "Create a sphere.",
            completed_query_id="Q001",
            completed_text="Create a cube.",
        ),
        settings,
    )

    result = retry_run("EXP001", "RUN001", client=FakeClient(), settings=settings)
    assert result["retried"] is True
    assert result["stopped"] is False

    run = get_run("EXP001", "RUN001", settings)
    assert run["status"] == "completed"
    assert all(query["status"] == "completed" for query in run["queries"])
    assert get_experiment("EXP001", settings)["status"] == "completed"


def test_retry_run_rejects_non_failed_run(settings):
    create_experiment("Retry Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    try:
        retry_run("EXP001", "RUN001", client=FakeClient(), settings=settings)
    except ValueError as exc:
        assert "no failed queries" in str(exc)
    else:
        raise AssertionError("Expected retry_run to reject a completed run")


def test_retry_run_rejects_when_already_running(settings):
    import threading

    from cadybara_benchmark.services.runs import _ActiveRun, _register_active_run, _unregister_active_run

    create_experiment("Retry Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_summary = _completed_run_with_failed_query("EXP001", "RUN001", "Q001", "Create a cube.")
    save_run_summary(run_summary, settings)

    cancel_event = threading.Event()
    active_run = _ActiveRun(
        experiment_id="EXP001",
        cancel_event=cancel_event,
        lock=threading.Lock(),
        run_summary=run_summary,
    )
    _register_active_run("RUN001", active_run)
    try:
        retry_run("EXP001", "RUN001", client=FakeClient(), settings=settings)
    except ValueError as exc:
        assert "already running" in str(exc)
    else:
        raise AssertionError("Expected retry_run to reject an already running run")
    finally:
        _unregister_active_run("RUN001")


def test_reconcile_finalizes_orphaned_completed_run(settings):
    create_experiment("Reconcile Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "running",
            "started_at": "2026-06-05T12:00:00Z",
            "finished_at": "",
            "parameters": {},
            "queries": [
                {
                    "query_id": "Q001",
                    "text": "Create a cube.",
                    "model": "default",
                    "images": [],
                    "status": "completed",
                    "error": {},
                    "artifact_dir": "",
                    "response_metadata": {},
                    "score": None,
                    "metrics": {},
                }
            ],
            "summary": {"completed": 1, "failed": 0},
        },
        settings,
    )

    reconciled = reconcile_persisted_run_state(get_run("EXP001", "RUN001", settings), settings=settings)
    assert reconciled["status"] == "completed"
    assert reconciled["finished_at"]


def test_reconcile_recovers_stopped_run_with_pending_queries_when_active_is_stale(settings):
    from cadybara_benchmark.services.runs import _ActiveRun, _register_active_run, _unregister_active_run

    create_experiment("Reconcile Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "stopped",
            "started_at": "2026-06-05T12:00:00Z",
            "finished_at": "2026-06-05T12:05:00Z",
            "parameters": {},
            "queries": [
                {
                    "query_id": "Q001",
                    "text": "Create a cube.",
                    "model": "default",
                    "images": [],
                    "status": "pending",
                    "error": {},
                    "artifact_dir": "",
                    "response_metadata": {},
                    "score": None,
                    "metrics": {},
                }
            ],
            "summary": {"completed": 0, "failed": 0},
        },
        settings,
    )

    stale_summary = {
        "id": "RUN001",
        "experiment_id": "EXP001",
        "status": "running",
        "started_at": "2026-06-05T12:00:00Z",
        "finished_at": "",
        "parameters": {},
        "queries": [
            {
                "query_id": "Q001",
                "text": "Create a cube.",
                "model": "default",
                "images": [],
                "status": "running",
                "error": {},
                "artifact_dir": "",
                "response_metadata": {},
                "score": None,
                "metrics": {},
            }
        ],
        "summary": {"completed": 0, "failed": 0},
    }
    _register_active_run(
        "RUN001",
        _ActiveRun(
            experiment_id="EXP001",
            cancel_event=threading.Event(),
            lock=threading.Lock(),
            run_summary=stale_summary,
        ),
    )

    reconciled = reconcile_persisted_run_state(get_run("EXP001", "RUN001", settings), settings=settings)
    assert reconciled["status"] == "stopped"
    assert reconciled["queries"][0]["status"] == "cancelled"
    _unregister_active_run("RUN001")


def test_reconcile_persisted_run_marks_orphaned_running_as_stopped(settings):
    from cadybara_benchmark.experiment_files import save_experiment

    create_experiment("Reconcile Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    add_query("EXP001", "Create a sphere.", settings=settings)

    run = {
        "id": "RUN001",
        "experiment_id": "EXP001",
        "status": "running",
        "started_at": "2026-06-05T12:00:00Z",
        "finished_at": "",
        "parameters": {},
        "queries": [
            {
                "query_id": "Q001",
                "text": "Create a cube.",
                "model": "default",
                "images": [],
                "status": "completed",
                "error": {},
                "artifact_dir": "",
                "response_metadata": {},
                "score": None,
                "metrics": {},
            },
            {
                "query_id": "Q002",
                "text": "Create a sphere.",
                "model": "default",
                "images": [],
                "status": "pending",
                "error": {},
                "artifact_dir": "",
                "response_metadata": {},
                "score": None,
                "metrics": {},
            },
        ],
        "summary": {"completed": 1, "failed": 0},
    }
    save_run_summary(run, settings)
    experiment = get_experiment("EXP001", settings)
    experiment["status"] = "running"
    save_experiment(experiment, settings)

    reconciled = reconcile_persisted_run_state(run, settings=settings)
    assert reconciled["status"] == "stopped"
    assert reconciled["finished_at"]
    assert reconciled["queries"][0]["status"] == "completed"
    assert reconciled["queries"][1]["status"] == "cancelled"
    assert reconciled["summary"] == {"completed": 1, "failed": 0}

    persisted = get_run("EXP001", "RUN001", settings)
    assert persisted["status"] == "stopped"
    assert get_experiment("EXP001", settings)["status"] == "stopped"


def test_reconcile_persisted_run_leaves_active_run_untouched(settings):
    create_experiment("Reconcile Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)

    client = BlockingClient()

    def execute() -> None:
        run_experiment("EXP001", client=client, settings=settings, concurrency=1)

    thread = threading.Thread(target=execute)
    thread.start()
    assert client.started.wait(timeout=5)

    run = get_run("EXP001", "RUN001", settings)
    reconciled = reconcile_persisted_run_state(run, settings=settings)
    assert reconciled["status"] == "running"

    stop_run("EXP001", "RUN001", settings=settings)
    client.release.set()
    thread.join(timeout=5)


def test_reconcile_persisted_run_noop_for_completed_run(settings):
    create_experiment("Reconcile Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    run_experiment("EXP001", client=FakeClient(), settings=settings)

    run = get_run("EXP001", "RUN001", settings)
    reconciled = reconcile_persisted_run_state(dict(run), settings=settings)
    assert reconciled["status"] == "completed"
    assert reconciled["queries"][0]["status"] == "completed"


def test_run_payload_reconciles_orphaned_run(settings, monkeypatch):
    _patch_settings(monkeypatch, settings)

    create_experiment("Reconcile Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)

    run = {
        "id": "RUN001",
        "experiment_id": "EXP001",
        "status": "running",
        "started_at": "2026-06-05T12:00:00Z",
        "finished_at": "",
        "parameters": {},
        "queries": [
            {
                "query_id": "Q001",
                "text": "Create a cube.",
                "model": "default",
                "images": [],
                "status": "running",
                "error": {},
                "artifact_dir": "",
                "response_metadata": {},
                "score": None,
                "metrics": {},
            }
        ],
        "summary": {"completed": 0, "failed": 0},
    }
    save_run_summary(run, settings)

    payload = _run_payload("EXP001", "RUN001")
    assert payload["status"] == "stopped"
    assert payload["queries"][0]["status"] == "cancelled"


def test_app_reconciles_run_when_expanding_row():
    script = (STATIC_DIR / "app.js").read_text()

    assert "async function toggleRunRow" in script
    assert "state.current = await api(`/api/experiments/${experimentId}`);" in script


def test_api_get_experiment_reconciles_orphaned_runs(settings, monkeypatch):
    from cadybara_benchmark.experiment_files import save_experiment
    from cadybara_benchmark.web import api_get_experiment

    _patch_settings(monkeypatch, settings)

    create_experiment("Reconcile Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "running",
            "started_at": "2026-06-05T12:00:00Z",
            "finished_at": "",
            "parameters": {},
            "queries": [
                {
                    "query_id": "Q001",
                    "text": "Create a cube.",
                    "model": "default",
                    "images": [],
                    "status": "running",
                    "error": {},
                    "artifact_dir": "",
                    "response_metadata": {},
                    "score": None,
                    "metrics": {},
                }
            ],
            "summary": {"completed": 0, "failed": 0},
        },
        settings,
    )
    experiment = get_experiment("EXP001", settings)
    experiment["status"] = "running"
    save_experiment(experiment, settings)

    payload = api_get_experiment("EXP001")
    assert payload["status"] == "stopped"
    assert payload["runs"][0]["status"] == "stopped"
    assert payload["runs"][0]["queries"][0]["status"] == "cancelled"


def test_reconcile_persisted_run_unregisters_stale_active_run(settings):
    from cadybara_benchmark.services.runs import _ActiveRun, _register_active_run

    create_experiment("Reconcile Test", settings=settings)
    add_query("EXP001", "Create a cube.", settings=settings)
    save_run_summary(
        {
            "id": "RUN001",
            "experiment_id": "EXP001",
            "status": "running",
            "started_at": "2026-06-05T12:00:00Z",
            "finished_at": "",
            "parameters": {},
            "queries": [
                {
                    "query_id": "Q001",
                    "text": "Create a cube.",
                    "model": "default",
                    "images": [],
                    "status": "pending",
                    "error": {},
                    "artifact_dir": "",
                    "response_metadata": {},
                    "score": None,
                    "metrics": {},
                }
            ],
            "summary": {"completed": 0, "failed": 0},
        },
        settings,
    )

    stale_summary = {
        "id": "RUN001",
        "experiment_id": "EXP001",
        "status": "stopped",
        "started_at": "2026-06-05T12:00:00Z",
        "finished_at": "2026-06-05T12:05:00Z",
        "parameters": {},
        "queries": [
            {
                "query_id": "Q001",
                "text": "Create a cube.",
                "model": "default",
                "images": [],
                "status": "cancelled",
                "error": {},
                "artifact_dir": "",
                "response_metadata": {},
                "score": None,
                "metrics": {},
            }
        ],
        "summary": {"completed": 0, "failed": 0},
    }
    _register_active_run(
        "RUN001",
        _ActiveRun(
            experiment_id="EXP001",
            cancel_event=threading.Event(),
            lock=threading.Lock(),
            run_summary=stale_summary,
        ),
    )

    run = get_run("EXP001", "RUN001", settings)
    reconciled = reconcile_persisted_run_state(run, settings=settings)
    assert reconciled["status"] == "stopped"
    assert reconciled["queries"][0]["status"] == "cancelled"


def test_app_collapses_long_run_query_text():
    script = (STATIC_DIR / "app.js").read_text()
    css = (STATIC_DIR / "app.css").read_text()
    shared = (STATIC_DIR / "query-text.js").read_text()

    assert 'from "./query-text.js"' in script
    assert "formatCollapsibleQueryText" in script
    assert "finalizeCollapsibleQueryTexts" in script
    assert "QUERY_TEXT_MAX_CHARS = 512" in shared
    assert "QUERY_TEXT_MAX_LINES = 3" in shared
    assert "-webkit-line-clamp: 3" in css
    assert "query-text-toggle.is-collapsed .query-text-preview" in css


def test_compare_layout_keeps_meta_visible():
    css = (STATIC_DIR / "compare.css").read_text()
    shared = (STATIC_DIR / "query-text.js").read_text()

    assert "min-width: 0" in css
    assert "compare-prompt-value" in css
    assert ".compare-meta .query-text-toggle.is-collapsed .query-text-preview" in css
    assert "prepareQueryTextToggle" in shared
    assert "getQueryTextRaw" in shared


def test_compare_collapses_long_query_text():
    script = (STATIC_DIR / "compare.js").read_text()

    assert 'from "./query-text.js"' in script
    assert "prepareQueryTextToggle" in script
    assert "formatCollapsibleQueryText(query.text, escapeHtml)" in script
    assert "finalizeCollapsibleQueryTexts(compareGrid)" in script
    assert "bindCollapsibleQueryText(compareGrid)" in script
    assert "compare-prompt-value" in script


def test_stl_viewer_collapses_long_query_text():
    script = (STATIC_DIR / "stl-viewer.js").read_text()

    assert 'from "./query-text.js"' in script
    assert "formatCollapsibleQueryText(query.text, escapeHtml)" in script
    assert "finalizeCollapsibleQueryTexts(text)" in script
    assert "bindCollapsibleQueryText(text)" in script


def test_app_route_resets_modal_backdrop():
    script = (STATIC_DIR / "app.js").read_text()

    route_start = script.index("async function route()")
    route_body = script[route_start : script.index("async function renderExperiments()")]
    assert "resetModalState();" in route_body

    reset_start = script.index("function resetModalState()")
    reset_body = script[reset_start : script.index("function escapeHtml")]
    assert '".modal-backdrop"' in reset_body
    assert '"modal-open"' in reset_body
