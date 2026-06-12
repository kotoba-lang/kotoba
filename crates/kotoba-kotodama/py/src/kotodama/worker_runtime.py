"""worker_runtime — shared building blocks for religious-corp Zeebe workers.

Per gate (a) §1 P3 of `/90-docs/2605211949-gate-a-execution-checklist.md`.

Provides 4 symbols used across all worker_main.py files in the religious-corp
port:

  - `watchdog(...)` — periodic liveness task body
  - `activation_monitor(url)` — checks BPMN activation count via XRPC
  - `task_sqlite_health_probe(...)` — pings a local SQLite path
  - `make_degraded_ingest_stub(name)` — factory returning a degraded-mode task
    that returns ``{"ok": True, "degraded": True, **kwargs}`` so that worker
    registration succeeds before the per-worker ingest module lands.

Per ADR-2605172000 (RW-free substrate): NO `psycopg`, NO `RisingWave`, NO
`vertex_*` SQL. All persistence is local SQLite under `$ORGANISM_SQLITE_DIR`
(default `/var/lib/etzhayyim/organism/`).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

_log = logging.getLogger(__name__)


def organism_sqlite_dir() -> Path:
    """Religious-corp SQLite root. Tests override via $ORGANISM_SQLITE_DIR."""
    return Path(os.environ.get("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism"))


async def watchdog(*, worker_name: str = "<unknown>") -> dict[str, Any]:
    """Periodic liveness task. Emits a structured liveness record + returns.

    Caller typically registers as ``worker.task(task_type="watchdog", ...)``.
    Smoke test asserts clean exit (return without raising).
    """
    now_ms = int(time.time() * 1000)
    _log.info("watchdog: worker=%s timestamp_ms=%d", worker_name, now_ms)
    return {"ok": True, "worker": worker_name, "timestamp_ms": now_ms}


async def activation_monitor(activation_url: str | None = None) -> dict[str, Any]:
    """Check BPMN activation count via XRPC at ``activation_url``.

    Bogus URLs return ``{"ok": False, "reason": "..."}`` rather than raise —
    we never want to take down the worker because the monitor URL is wrong.
    """
    if not activation_url or not activation_url.startswith(("http://", "https://")):
        return {"ok": False, "reason": "no_url_or_invalid_scheme", "url": activation_url or ""}
    try:
        import httpx
    except ImportError:
        return {"ok": False, "reason": "httpx_not_installed"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(activation_url)
        return {"ok": resp.status_code < 400, "status": resp.status_code}
    except Exception as e:
        return {"ok": False, "reason": "request_failed", "error": str(e)}


async def task_sqlite_health_probe(*, db_path: str | None = None) -> dict[str, Any]:
    """Ping a local SQLite path. Returns ``{"ok": True/False, ...}`` always.

    If ``db_path`` is missing the directory but is writable, creates an empty
    DB and returns healthy. If the directory itself is not writable, returns
    ``ok=False`` with ``reason="directory_not_writable"``.
    """
    if db_path is None:
        db_path = str(organism_sqlite_dir() / "healthz.db")
    path = Path(db_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as e:
        return {"ok": False, "reason": "directory_not_writable", "error": str(e)}
    try:
        conn = sqlite3.connect(str(path))
        conn.execute("CREATE TABLE IF NOT EXISTS _healthz (ts INTEGER)")
        conn.execute("INSERT INTO _healthz (ts) VALUES (?)", (int(time.time()),))
        conn.commit()
        (count,) = conn.execute("SELECT COUNT(*) FROM _healthz").fetchone()
        conn.close()
        return {"ok": True, "path": str(path), "row_count": int(count)}
    except sqlite3.Error as e:
        return {"ok": False, "reason": "sqlite_error", "error": str(e)}


def make_degraded_ingest_stub(name: str) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Factory: returns an async task that always returns degraded-mode payload.

    Used while the per-worker ingest module is still being ported. The worker
    registration succeeds; calls just return ``{"ok": True, "degraded": True,
    **kwargs}`` so callers can detect degraded mode.
    """

    async def _stub(**kwargs: Any) -> dict[str, Any]:
        _log.info("degraded_stub: name=%s kwargs=%r", name, kwargs)
        return {"ok": True, "degraded": True, "stub": name, **kwargs}

    _stub.__name__ = f"degraded_stub_{name}"
    return _stub


__all__ = [
    "organism_sqlite_dir",
    "watchdog",
    "activation_monitor",
    "task_sqlite_health_probe",
    "make_degraded_ingest_stub",
]
