"""Tests for langgraph_watcher (Phase 4 — hot reload)."""
from __future__ import annotations

import asyncio
import json
import sys
import types
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


def _cursor(rows):
    cur = MagicMock()
    cur.fetchall = AsyncMock(return_value=rows)
    cur.fetchone = AsyncMock(return_value=rows[0] if rows else None)
    return cur


def _pool_with_cursors(cursor_queue: list[MagicMock]):
    """Build pool whose conn.execute() returns cursors in declared order."""
    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=cursor_queue)

    @asynccontextmanager
    async def _cm():
        yield conn

    pool = MagicMock()
    pool.connection = _cm
    return pool, conn


async def _afact(pool):
    return pool


# ---------------------------------------------------------------------------
# Fake factory module for py_factory rows.
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_factory_module():
    mod = types.ModuleType("kotodama_test_watcher_factory")
    sentinel_v1 = ("v1", object())
    sentinel_v2 = ("v2", object())
    mod._current = sentinel_v1
    mod.build_graph = lambda: mod._current  # type: ignore[attr-defined]
    sys.modules["kotodama_test_watcher_factory"] = mod
    yield mod, sentinel_v1, sentinel_v2
    sys.modules.pop("kotodama_test_watcher_factory", None)


# ---------------------------------------------------------------------------
# 1. add — new active deployment registers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_active_row_registers(fake_factory_module):
    from kotodama.langgraph_watcher import _reconcile_once

    mod, sentinel, _ = fake_factory_module
    deploy_cursor = _cursor([("aid_new", 1, "active", "ts1")])
    assistant_cursor = _cursor([("py_factory", "kotodama_test_watcher_factory", None, "active")])
    pool, _ = _pool_with_cursors([deploy_cursor, assistant_cursor])

    registry: dict = {}
    last_seen = await _reconcile_once(
        pool_factory=lambda: _afact(pool),
        register_fn=lambda aid, g: registry.update({aid: g}),
        pop_fn=lambda aid: registry.pop(aid, None),
        last_seen={},
    )
    assert registry["aid_new"] == sentinel
    assert last_seen == {"aid_new": (1, "active", "ts1")}


# ---------------------------------------------------------------------------
# 2. remove — status='disabled' triggers pop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disable_evicts(fake_factory_module):
    from kotodama.langgraph_watcher import _reconcile_once

    deploy_cursor = _cursor([("aid_x", 1, "disabled", "ts2")])
    pool, _ = _pool_with_cursors([deploy_cursor])

    registry = {"aid_x": "old_graph"}
    await _reconcile_once(
        pool_factory=lambda: _afact(pool),
        register_fn=lambda aid, g: registry.update({aid: g}),
        pop_fn=lambda aid: registry.pop(aid, None),
        last_seen={"aid_x": (1, "active", "ts1")},
    )
    assert "aid_x" not in registry


# ---------------------------------------------------------------------------
# 3. version swap — new version recompiles and replaces
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_version_swap_replaces(fake_factory_module):
    from kotodama.langgraph_watcher import _reconcile_once

    mod, sentinel_v1, sentinel_v2 = fake_factory_module
    mod._current = sentinel_v2  # factory now returns v2

    deploy_cursor = _cursor([("aid_x", 2, "active", "ts3")])
    assistant_cursor = _cursor([("py_factory", "kotodama_test_watcher_factory", None, "active")])
    pool, _ = _pool_with_cursors([deploy_cursor, assistant_cursor])

    registry = {"aid_x": sentinel_v1}
    await _reconcile_once(
        pool_factory=lambda: _afact(pool),
        register_fn=lambda aid, g: registry.update({aid: g}),
        pop_fn=lambda aid: registry.pop(aid, None),
        last_seen={"aid_x": (1, "active", "ts1")},
    )
    assert registry["aid_x"] == sentinel_v2


# ---------------------------------------------------------------------------
# 4. no-op poll — diff unchanged → no register/pop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unchanged_poll_noop():
    from kotodama.langgraph_watcher import _reconcile_once

    deploy_cursor = _cursor([("aid_x", 1, "active", "ts1")])
    pool, _ = _pool_with_cursors([deploy_cursor])

    registry = {"aid_x": "graph_v1"}
    register_calls: list = []
    pop_calls: list = []
    await _reconcile_once(
        pool_factory=lambda: _afact(pool),
        register_fn=lambda aid, g: register_calls.append((aid, g)),
        pop_fn=lambda aid: pop_calls.append(aid),
        last_seen={"aid_x": (1, "active", "ts1")},
    )
    assert register_calls == []
    assert pop_calls == []


# ---------------------------------------------------------------------------
# 5. broken row — failed compile keeps prior graph in place
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compile_failure_does_not_evict():
    from kotodama.langgraph_watcher import _reconcile_once

    deploy_cursor = _cursor([("aid_x", 2, "active", "ts2")])
    # assistant row points at non-existent module → import fails
    assistant_cursor = _cursor([("py_factory", "kotodama_test_watcher_NONEXISTENT", None, "active")])
    pool, _ = _pool_with_cursors([deploy_cursor, assistant_cursor])

    registry = {"aid_x": "old_graph"}
    await _reconcile_once(
        pool_factory=lambda: _afact(pool),
        register_fn=lambda aid, g: registry.update({aid: g}),
        pop_fn=lambda aid: registry.pop(aid, None),
        last_seen={"aid_x": (1, "active", "ts1")},
    )
    # Old graph survives — register_fn was not called with anything new.
    assert registry == {"aid_x": "old_graph"}


# ---------------------------------------------------------------------------
# 6. row deletion (in last_seen, not in current) — evicts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_row_deletion_evicts():
    from kotodama.langgraph_watcher import _reconcile_once

    deploy_cursor = _cursor([])  # nothing in deployment table
    pool, _ = _pool_with_cursors([deploy_cursor])

    registry = {"aid_x": "graph_v1"}
    await _reconcile_once(
        pool_factory=lambda: _afact(pool),
        register_fn=lambda aid, g: registry.update({aid: g}),
        pop_fn=lambda aid: registry.pop(aid, None),
        last_seen={"aid_x": (1, "active", "ts1")},
    )
    assert "aid_x" not in registry


# ---------------------------------------------------------------------------
# 7. concurrent diff — last write wins (no interleaving corruption)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_reconcile_last_write_wins(fake_factory_module):
    """Two _reconcile_once calls racing — refcount semantics keep state sane."""
    from kotodama.langgraph_watcher import _reconcile_once

    mod, sentinel_v1, sentinel_v2 = fake_factory_module

    # First reconcile uses sentinel_v1.
    mod._current = sentinel_v1
    deploy_a = _cursor([("aid_x", 1, "active", "ts1")])
    asst_a = _cursor([("py_factory", "kotodama_test_watcher_factory", None, "active")])
    pool_a, _ = _pool_with_cursors([deploy_a, asst_a])

    # Second sees v2.
    mod._current = sentinel_v2
    deploy_b = _cursor([("aid_x", 2, "active", "ts2")])
    asst_b = _cursor([("py_factory", "kotodama_test_watcher_factory", None, "active")])
    pool_b, _ = _pool_with_cursors([deploy_b, asst_b])

    registry: dict = {}
    register_lock = asyncio.Lock()
    async def _register(aid, g):
        async with register_lock:
            registry[aid] = g

    # Synchronous register_fn since _reconcile_once is sync inside.
    def _reg_sync(aid, g):
        registry[aid] = g

    res_a, res_b = await asyncio.gather(
        _reconcile_once(lambda: _afact(pool_a), _reg_sync, lambda aid: registry.pop(aid, None), {}),
        _reconcile_once(lambda: _afact(pool_b), _reg_sync, lambda aid: registry.pop(aid, None), {}),
    )
    # One of the two writes lands last; both sentinels are valid graph refs.
    assert registry["aid_x"] in (sentinel_v1, sentinel_v2)


# ---------------------------------------------------------------------------
# 8. WatcherStats reload_count increments on success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_reload_count_increments(fake_factory_module):
    from kotodama.langgraph_watcher import _reconcile_once, STATS

    STATS.reload_count = 0
    STATS.error_count = 0

    deploy_cursor = _cursor([("aid_y", 1, "active", "ts1")])
    asst_cursor = _cursor([("py_factory", "kotodama_test_watcher_factory", None, "active")])
    pool, _ = _pool_with_cursors([deploy_cursor, asst_cursor])

    registry = {}
    await _reconcile_once(
        pool_factory=lambda: _afact(pool),
        register_fn=lambda aid, g: registry.update({aid: g}),
        pop_fn=lambda aid: registry.pop(aid, None),
        last_seen={},
    )
    assert STATS.reload_count == 1
    assert STATS.last_reload_at > 0


# ---------------------------------------------------------------------------
# 9. error_count increments on broken row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_error_count_increments_on_broken_row():
    from kotodama.langgraph_watcher import _reconcile_once, STATS

    STATS.reload_count = 0
    STATS.error_count = 0

    deploy_cursor = _cursor([("aid_z", 1, "active", "ts1")])
    asst_cursor = _cursor([("py_factory", "kotodama_test_watcher_NONEXISTENT", None, "active")])
    pool, _ = _pool_with_cursors([deploy_cursor, asst_cursor])

    registry = {}
    await _reconcile_once(
        pool_factory=lambda: _afact(pool),
        register_fn=lambda aid, g: registry.update({aid: g}),
        pop_fn=lambda aid: registry.pop(aid, None),
        last_seen={},
    )
    assert STATS.reload_count == 0
    assert STATS.error_count == 1
    assert "aid_z" not in registry
