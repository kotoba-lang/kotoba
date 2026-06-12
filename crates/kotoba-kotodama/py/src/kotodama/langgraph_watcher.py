"""Hot-reload watcher for vertex_langgraph_deployment (ADR-2605080600 Phase 4).

Polls the deployment table at a fixed interval and reconciles the in-process
``_GRAPH_REGISTRY`` against active rows. New / changed deployments compile and
register; disabled / removed deployments evict.

Design (per advisor review):

- **Diff key** = ``(version, status, updated_at)`` per ``assistant_id``.
  ``_seq`` is unreliable in RW (does not auto-advance on PK upsert; always
  contains the value the writer INSERTed). ``updated_at`` is set explicitly
  by all callers (P1 seed, manual deploy, etc.) and IS the change signal.

- **Lazy fetch** — the periodic poll touches only the deployment table.
  The full assistant row + node bindings are fetched only for assistant_ids
  whose diff key changed.

- **Compile-then-swap** — a failed compile leaves the prior graph in place
  (``_GRAPH_REGISTRY[aid] = new_graph`` only on successful build). In-flight
  ``_execute_graph`` runs hold their own local reference to the old graph,
  so refcount keeps them alive past the swap. Disable/delete pops the entry
  immediately; new ``/runs`` 404, in-flight runs continue.

- **Error-trapped loop** — every poll iteration is wrapped in
  ``try/except Exception`` so a transient RW connection blip merely delays
  one tick.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Awaitable, Callable

from kotodama.langgraph_loader import (
    _compile_topology,
    _resolve_factory,
    _SELECT_NODES_SQL,
)

LOG = logging.getLogger("langgraph_watcher")

DEFAULT_INTERVAL_SEC = 30


_POLL_DEPLOYMENTS_SQL = """
SELECT d.assistant_id, d.version, d.status, d.updated_at
FROM vertex_langgraph_deployment d
"""

_FETCH_ASSISTANT_SQL = """
SELECT a.kind, a.factory_path, a.spec, d.status
FROM vertex_langgraph_assistant a
JOIN vertex_langgraph_deployment d
  ON d.assistant_id = a.assistant_id AND d.version = a.version
WHERE a.assistant_id = %s AND a.version = %s
"""


class WatcherStats:
    """Mutable counters exposed via /registry-source."""

    def __init__(self) -> None:
        self.last_reload_at: int = 0      # ms epoch
        self.reload_count: int = 0
        self.error_count: int = 0
        self.running: bool = False
        # Map of assistant_id → most-recent reload error (compile / fetch).
        # Cleared per-aid on next successful reload of that aid.
        self.errored: dict[str, str] = {}

    def to_dict(self) -> dict:
        return {
            "running": self.running,
            "last_reload_at": self.last_reload_at,
            "reload_count": self.reload_count,
            "error_count": self.error_count,
            "errored_assistants": [
                {"assistant_id": aid, "error": msg}
                for aid, msg in sorted(self.errored.items())
            ],
        }


# Module-level singleton so /registry-source can read without plumbing.
STATS = WatcherStats()


async def _fetch_active_deployments(conn: Any) -> dict[str, tuple]:
    """Return {assistant_id: (version, status, updated_at)} for ALL rows."""
    cur = await conn.execute(_POLL_DEPLOYMENTS_SQL, prepare=False)
    out: dict[str, tuple] = {}
    for row in await cur.fetchall():
        aid, version, status, updated_at = row
        out[aid] = (version, status, updated_at)
    return out


async def _fetch_assistant_and_bindings(conn: Any, assistant_id: str, version: int) -> tuple[Any, list[tuple]]:
    cur = await conn.execute(_FETCH_ASSISTANT_SQL, (assistant_id, version), prepare=False)
    row = await cur.fetchone()
    if row is None:
        raise ValueError(f"{assistant_id} v{version}: assistant row not found")
    kind, factory_path, spec, _status = row

    bindings: list[tuple] = []
    if kind == "topology":
        bcur = await conn.execute(_SELECT_NODES_SQL, (assistant_id,), prepare=False)
        bindings = list(await bcur.fetchall())

    return (kind, factory_path, spec), bindings


async def _build_graph(
    assistant_id: str,
    payload: tuple,
    bindings: list[tuple],
    pool_factory: Callable[[], Awaitable[Any]],
) -> Any:
    kind, factory_path, spec = payload
    if kind == "py_factory":
        if not factory_path:
            raise ValueError("py_factory missing factory_path")
        return _resolve_factory(factory_path)
    if kind == "single_task":
        if not factory_path:
            raise ValueError("single_task missing factory_path")
        from kotodama.langgraph_graphs._single_task_wrapper import (
            build_single_task_graph,
        )
        from kotodama.langgraph_loader import _resolve_callable as _rc
        return build_single_task_graph(_rc(factory_path))
    if kind == "topology":
        if not spec:
            raise ValueError("topology missing spec")
        import json
        spec_obj = json.loads(spec) if isinstance(spec, str) else spec
        if not bindings:
            raise ValueError(f"topology {assistant_id} has no node bindings")
        return _compile_topology(assistant_id, spec_obj, bindings, pool_factory=pool_factory)
    raise NotImplementedError(f"unknown assistant kind: {kind!r}")


async def _reconcile_once(
    pool_factory: Callable[[], Awaitable[Any]],
    register_fn: Callable[[str, Any], None],
    pop_fn: Callable[[str], None],
    last_seen: dict[str, tuple],
) -> dict[str, tuple]:
    """One poll cycle. Returns the new ``last_seen`` snapshot."""
    pool = await pool_factory()
    async with pool.connection() as conn:
        current = await _fetch_active_deployments(conn)

        # Detect adds / updates
        for aid, key in current.items():
            if last_seen.get(aid) == key:
                continue  # no change
            version, status, _ts = key
            if status != "active":
                # Not active — ensure it's evicted from registry.
                pop_fn(aid)
                LOG.info("watcher: %s status=%s → evicted", aid, status)
                continue
            try:
                payload, bindings = await _fetch_assistant_and_bindings(conn, aid, version)
                graph = await _build_graph(aid, payload, bindings, pool_factory)
                register_fn(aid, graph)
                STATS.reload_count += 1
                STATS.errored.pop(aid, None)
                LOG.info("watcher: reloaded %s v%s", aid, version)
            except Exception as exc:
                STATS.error_count += 1
                STATS.errored[aid] = f"{type(exc).__name__}: {exc}"
                LOG.warning("watcher: failed to reload %s v%s: %s", aid, version, exc)

        # Detect deletions (in last_seen but not in current).
        for aid in set(last_seen) - set(current):
            pop_fn(aid)
            LOG.info("watcher: %s removed from deployment table → evicted", aid)

    STATS.last_reload_at = int(time.time() * 1000)
    return current


async def watch_forever(
    pool_factory: Callable[[], Awaitable[Any]],
    register_fn: Callable[[str, Any], None],
    pop_fn: Callable[[str], None],
    interval_sec: float | None = None,
    *,
    initial_seen: dict[str, tuple] | None = None,
) -> None:
    """Start the polling loop. Intended to be wrapped with asyncio.create_task."""
    if interval_sec is None:
        interval_sec = float(os.environ.get("LANGGRAPH_RELOAD_INTERVAL_SEC", DEFAULT_INTERVAL_SEC))
    last_seen: dict[str, tuple] = dict(initial_seen or {})
    STATS.running = True
    LOG.info("langgraph_watcher: starting (interval=%.1fs, initial_seen=%d)",
             interval_sec, len(last_seen))
    try:
        while True:
            try:
                last_seen = await _reconcile_once(pool_factory, register_fn, pop_fn, last_seen)
            except Exception as exc:
                STATS.error_count += 1
                LOG.warning("langgraph_watcher: poll failed (will retry): %s", exc)
            await asyncio.sleep(interval_sec)
    except asyncio.CancelledError:
        LOG.info("langgraph_watcher: cancelled")
        raise
    finally:
        STATS.running = False
