"""Tests for etzhayyim_sdk.metrics — in-process metrics collector.

Per ADR-2605215200 §monitoring.
"""

from __future__ import annotations

import threading
import time

import pytest

from etzhayyim_sdk import metrics


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Reset global metrics state before each test."""
    metrics.reset()
    yield
    metrics.reset()


# ── test_counter_inc ──────────────────────────────────────────────────────────


def test_counter_inc():
    c = metrics.counter("test.counter")
    c.inc()
    c.inc(4)
    output = metrics.export_prometheus()
    assert "test_counter 5" in output


# ── test_gauge_set_inc ────────────────────────────────────────────────────────


def test_gauge_set_inc():
    g = metrics.gauge("test.gauge")
    g.set(10.0)
    g.inc(3.5)
    output = metrics.export_prometheus()
    assert "test_gauge 13.5" in output


# ── test_observe_histogram ────────────────────────────────────────────────────


def test_observe_histogram():
    for v in [0.1, 0.2, 0.3, 0.4, 0.5]:
        metrics.observe("test.hist", v)
    output = metrics.export_prometheus()
    assert "test_hist_count 5" in output
    assert "test_hist_sum" in output
    assert "test_hist_p50" in output
    assert "test_hist_p95" in output
    assert "test_hist_p99" in output


# ── test_timer_context ────────────────────────────────────────────────────────


def test_timer_context():
    with metrics.timer("test.latency"):
        time.sleep(0.01)
    output = metrics.export_prometheus()
    assert "test_latency_count 1" in output
    assert "test_latency_sum" in output


# ── test_export_prometheus_format ─────────────────────────────────────────────


def test_export_prometheus_format():
    metrics.counter("svc.requests").inc(7)
    metrics.gauge("svc.queue_depth").set(3.0)
    metrics.observe("svc.duration", 0.042)

    output = metrics.export_prometheus()

    # Counter
    assert "# TYPE svc_requests counter" in output
    assert "svc_requests 7" in output
    # Gauge
    assert "# TYPE svc_queue_depth gauge" in output
    assert "svc_queue_depth 3.0" in output
    # Histogram
    assert "# TYPE svc_duration histogram" in output
    assert "svc_duration_count 1" in output
    # Output ends with newline
    assert output.endswith("\n")


# ── test_reset ────────────────────────────────────────────────────────────────


def test_reset():
    metrics.counter("x.c").inc(5)
    metrics.gauge("x.g").set(9.0)
    metrics.observe("x.h", 1.0)

    metrics.reset()
    output = metrics.export_prometheus()

    assert "x_c" not in output
    assert "x_g" not in output
    assert "x_h" not in output
    # After reset the output is just a newline (empty metric set)
    assert output == "\n"


# ── test_thread_safety ────────────────────────────────────────────────────────


def test_thread_safety():
    """Concurrent increments from multiple threads must not lose counts."""
    n_threads = 20
    incs_per_thread = 500

    def _worker():
        c = metrics.counter("thread.safety.counter")
        for _ in range(incs_per_thread):
            c.inc()

    threads = [threading.Thread(target=_worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    output = metrics.export_prometheus()
    expected = n_threads * incs_per_thread
    assert f"thread_safety_counter {expected}" in output
