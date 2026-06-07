"""Pure tests for langgraph_loader (ADR-2605080600 amendment — RW deployment SSoT).

No RisingWave, no real psycopg. Mocks the AsyncConnectionPool API surface
that load_active_graphs() touches: ``async with pool.connection() as conn``
+ ``conn.execute(sql)`` returning a cursor with ``fetchall()``.
"""
from __future__ import annotations

import sys
import types
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fake pool helpers
# ---------------------------------------------------------------------------


def _make_pool(rows: list[tuple]):
    """Build an object exposing the AsyncConnectionPool surface used by loader."""
    cur = MagicMock()
    cur.fetchall = AsyncMock(return_value=rows)
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=cur)

    @asynccontextmanager
    async def _conn_cm():
        yield conn

    pool = MagicMock()
    pool.connection = _conn_cm
    return pool


async def _pool_factory(pool):
    return pool


# ---------------------------------------------------------------------------
# Fake factory module — installed into sys.modules so importlib resolves it.
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_factory_module():
    mod = types.ModuleType("kotodama_test_fake_factory")
    sentinel = object()
    mod.build_graph = lambda: sentinel  # type: ignore[attr-defined]
    sys.modules["kotodama_test_fake_factory"] = mod
    yield mod, sentinel
    sys.modules.pop("kotodama_test_fake_factory", None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loads_py_factory_and_registers(fake_factory_module):
    from kotodama.langgraph_loader import load_active_graphs

    _mod, sentinel = fake_factory_module
    rows = [("ki_cycle_v2", 1, "py_factory", "kotodama_test_fake_factory", None, "active", "ts1")]
    pool = _make_pool(rows)
    registered: dict[str, object] = {}

    result = await load_active_graphs(
        pool_factory=lambda: _pool_factory(pool),
        register_fn=lambda aid, g: registered.update({aid: g}),
    )

    result.pop("seen", None); assert result == {"loaded": 1, "skipped_existing": 0, "errors": 0}
    assert registered == {"ki_cycle_v2": sentinel}


@pytest.mark.asyncio
async def test_skips_already_registered(fake_factory_module):
    from kotodama.langgraph_loader import load_active_graphs

    rows = [("ki_cycle", 1, "py_factory", "kotodama_test_fake_factory", None, "active", "ts1")]
    pool = _make_pool(rows)
    registered: dict[str, object] = {}

    result = await load_active_graphs(
        pool_factory=lambda: _pool_factory(pool),
        register_fn=lambda aid, g: registered.update({aid: g}),
        already_registered=lambda aid: aid == "ki_cycle",
    )

    result.pop("seen", None); assert result == {"loaded": 0, "skipped_existing": 1, "errors": 0}
    assert registered == {}


@pytest.mark.asyncio
async def test_unknown_kind_is_error_not_crash():
    from kotodama.langgraph_loader import load_active_graphs

    rows = [("future_graph", 1, "topology", None, "{}", "active", "ts1")]
    pool = _make_pool(rows)
    registered: dict[str, object] = {}

    result = await load_active_graphs(
        pool_factory=lambda: _pool_factory(pool),
        register_fn=lambda aid, g: registered.update({aid: g}),
    )

    assert result["loaded"] == 0
    assert result["errors"] == 1
    assert registered == {}


@pytest.mark.asyncio
async def test_missing_table_is_noop():
    from kotodama.langgraph_loader import load_active_graphs

    @asynccontextmanager
    async def _conn_cm():
        conn = MagicMock()
        conn.execute = AsyncMock(side_effect=Exception("relation does not exist"))
        yield conn

    pool = MagicMock()
    pool.connection = _conn_cm

    result = await load_active_graphs(
        pool_factory=lambda: _pool_factory(pool),
        register_fn=lambda aid, g: None,
    )

    result.pop("seen", None); assert result == {"loaded": 0, "skipped_existing": 0, "errors": 0}


@pytest.mark.asyncio
async def test_pool_unavailable_is_noop():
    from kotodama.langgraph_loader import load_active_graphs

    async def _broken_factory():
        raise RuntimeError("RW_URL not set")

    result = await load_active_graphs(
        pool_factory=_broken_factory,
        register_fn=lambda aid, g: None,
    )

    result.pop("seen", None); assert result == {"loaded": 0, "skipped_existing": 0, "errors": 0}


@pytest.mark.asyncio
async def test_factory_path_with_explicit_attr(fake_factory_module):
    from kotodama.langgraph_loader import load_active_graphs

    _mod, sentinel = fake_factory_module
    # Use the colon syntax to pin attribute name.
    rows = [("explicit_attr", 1, "py_factory", "kotodama_test_fake_factory:build_graph", None, "active", "ts1")]
    pool = _make_pool(rows)
    registered: dict[str, object] = {}

    result = await load_active_graphs(
        pool_factory=lambda: _pool_factory(pool),
        register_fn=lambda aid, g: registered.update({aid: g}),
    )

    assert result["loaded"] == 1
    assert registered["explicit_attr"] is sentinel


# ---------------------------------------------------------------------------
# _resolve_checkpointer  (ADR-2605082100)
# ---------------------------------------------------------------------------


def test_resolve_checkpointer_none_returns_none():
    from kotodama.langgraph_loader import _resolve_checkpointer
    assert _resolve_checkpointer(None) is None
    assert _resolve_checkpointer("") is None
    assert _resolve_checkpointer("none") is None


def test_resolve_checkpointer_unknown_mode_returns_none():
    from kotodama.langgraph_loader import _resolve_checkpointer
    # Defensive — unknown modes must not block loading.
    assert _resolve_checkpointer("redis") is None


def test_resolve_checkpointer_postgres_without_dsn_returns_none(monkeypatch):
    from kotodama.langgraph_loader import _resolve_checkpointer
    monkeypatch.delenv("HYPERDRIVE_LANGGRAPH_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert _resolve_checkpointer("postgres") is None


def test_resolve_checkpointer_rw_vertex_swallows_init_error(monkeypatch):
    """rw_vertex saver init failure must downgrade to None, not crash the loader."""
    import sys
    import types
    from kotodama.langgraph_loader import _resolve_checkpointer

    fake = types.ModuleType("kotodama.langgraph_checkpoint_rw")
    class _Boom:
        def __init__(self):
            raise RuntimeError("simulated init failure")
    fake.RisingWaveCheckpointSaver = _Boom
    monkeypatch.setitem(sys.modules, "kotodama.langgraph_checkpoint_rw", fake)
    assert _resolve_checkpointer("rw_vertex") is None
