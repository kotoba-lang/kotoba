"""Simple in-process metrics collector for religious-corp services.

Tracks counters + histograms in memory. Exposes /metrics endpoint in
Prometheus text-format for scraping. Per ADR-2605215200 §monitoring.

Usage:
    from etzhayyim_sdk import metrics

    metrics.counter("shinka.heartbeat.fired").inc()
    with metrics.timer("shinka.observation.latency"):
        ...

    # Expose:
    @app.router.get("/metrics")
    async def metrics_endpoint(request):
        return web.Response(text=metrics.export_prometheus(), content_type="text/plain")
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Iterator
import logging

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_counters: dict[str, int] = {}
_gauges: dict[str, float] = {}
_histograms: dict[str, list[float]] = {}


class _Counter:
    def __init__(self, name: str):
        self.name = name

    def inc(self, n: int = 1) -> None:
        with _lock:
            _counters[self.name] = _counters.get(self.name, 0) + n


class _Gauge:
    def __init__(self, name: str):
        self.name = name

    def set(self, value: float) -> None:
        with _lock:
            _gauges[self.name] = value

    def inc(self, n: float = 1.0) -> None:
        with _lock:
            _gauges[self.name] = _gauges.get(self.name, 0.0) + n


def counter(name: str) -> _Counter:
    return _Counter(name)


def gauge(name: str) -> _Gauge:
    return _Gauge(name)


def observe(name: str, value: float) -> None:
    """Add a value to a histogram."""
    with _lock:
        if name not in _histograms:
            _histograms[name] = []
        _histograms[name].append(value)
        # Trim to last 1000 samples to bound memory
        if len(_histograms[name]) > 1000:
            _histograms[name] = _histograms[name][-1000:]


@contextmanager
def timer(name: str) -> Iterator[None]:
    """Context manager: time the block, record as histogram in seconds."""
    start = time.perf_counter()
    try:
        yield
    finally:
        observe(name, time.perf_counter() - start)


def export_prometheus() -> str:
    """Export current metrics in Prometheus text format."""
    lines: list[str] = []
    with _lock:
        for name, value in sorted(_counters.items()):
            metric_name = name.replace(".", "_")
            lines.append(f"# TYPE {metric_name} counter")
            lines.append(f"{metric_name} {value}")
        for name, value in sorted(_gauges.items()):
            metric_name = name.replace(".", "_")
            lines.append(f"# TYPE {metric_name} gauge")
            lines.append(f"{metric_name} {value}")
        for name, values in sorted(_histograms.items()):
            metric_name = name.replace(".", "_")
            lines.append(f"# TYPE {metric_name} histogram")
            count = len(values)
            total = sum(values)
            lines.append(f"{metric_name}_count {count}")
            lines.append(f"{metric_name}_sum {total}")
            if values:
                sorted_vals = sorted(values)
                p50 = sorted_vals[len(sorted_vals) // 2]
                p95 = sorted_vals[int(len(sorted_vals) * 0.95)]
                p99 = sorted_vals[int(len(sorted_vals) * 0.99)]
                lines.append(f"{metric_name}_p50 {p50}")
                lines.append(f"{metric_name}_p95 {p95}")
                lines.append(f"{metric_name}_p99 {p99}")
    return "\n".join(lines) + "\n"


def reset() -> None:
    """Reset all metrics (test-only)."""
    with _lock:
        _counters.clear()
        _gauges.clear()
        _histograms.clear()
