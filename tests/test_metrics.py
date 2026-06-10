from __future__ import annotations

from cadybara_benchmark.metrics import (
    average_client_latency_ms,
    client_latency_ms,
    run_eta_ms,
    total_client_latency_ms,
)


def test_client_latency_ms_from_response_metadata():
    assert client_latency_ms({"response_metadata": {"latency_ms": 1234}}) == 1234


def test_client_latency_ms_from_error_payload():
    assert client_latency_ms({"error": {"latency_ms": 567}}) == 567


def test_client_latency_ms_prefers_response_metadata():
    query = {
        "response_metadata": {"latency_ms": 100},
        "error": {"latency_ms": 999},
    }
    assert client_latency_ms(query) == 100


def test_client_latency_ms_missing():
    assert client_latency_ms({}) is None
    assert client_latency_ms({"response_metadata": {"latency_ms": "100"}}) is None


def test_average_client_latency_ms():
    queries = [
        {"response_metadata": {"latency_ms": 100}},
        {"response_metadata": {"latency_ms": 200}},
        {},
    ]
    assert average_client_latency_ms(queries) == 150


def test_average_client_latency_ms_empty():
    assert average_client_latency_ms([]) is None
    assert average_client_latency_ms([{}]) is None


def test_total_client_latency_ms():
    queries = [
        {"response_metadata": {"latency_ms": 100}},
        {"response_metadata": {"latency_ms": 250}},
        {},
    ]
    assert total_client_latency_ms(queries) == 350


def test_total_client_latency_ms_empty():
    assert total_client_latency_ms([]) is None
    assert total_client_latency_ms([{}]) is None


def test_run_eta_ms():
    queries = [
        {"status": "completed", "response_metadata": {"latency_ms": 100}},
        {"status": "failed", "error": {"latency_ms": 200}},
        {"status": "running"},
        {"status": "pending"},
    ]
    assert run_eta_ms(queries) == 300


def test_run_eta_ms_without_finished_queries():
    queries = [
        {"status": "running"},
        {"status": "pending"},
    ]
    assert run_eta_ms(queries) is None
