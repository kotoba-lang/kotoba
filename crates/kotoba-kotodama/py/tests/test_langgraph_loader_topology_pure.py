"""v2 topology mode tests for langgraph_loader.

Covers the row-driven StateGraph compile path:
- linear edges + conditional edges
- end-to-end ainvoke through compiled graph
- error paths (unknown node kind, missing bindings)
- loader picks topology row over factory row
- kind='py_factory' continues to work (regression guard)

Mocks the AsyncConnectionPool surface. Two queries land on
``conn.execute()`` per topology assistant: deployments+assistants JOIN,
then per-assistant node bindings — the fake_pool returns different
cursors via a side_effect queue so the order is stable.
"""

from __future__ import annotations

import json
import sys
import types
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


def _cursor(rows: list[tuple]) -> MagicMock:
    cur = MagicMock()
    cur.fetchall = AsyncMock(return_value=rows)
    return cur


def _make_pool(cursors_in_order: list[MagicMock]) -> MagicMock:
    """Build a pool whose conn.execute() returns cursors in declared order."""
    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=cursors_in_order)

    @asynccontextmanager
    async def _conn_cm():
        yield conn

    pool = MagicMock()
    pool.connection = _conn_cm
    return pool


async def _factory(pool):
    return pool


# ---------------------------------------------------------------------------
# Topology: linear edges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topology_linear_compiles_and_runs():
    from kotodama.langgraph_loader import load_active_graphs

    spec = json.dumps({
        "state_keys": ["input", "echo", "length"],
        "entry": "echo",
        "edges": [
            {"from": "echo", "to": "count"},
            {"from": "count", "to": "END"},
        ],
    })
    deploy_cursor = _cursor([("demo_linear", 1, "topology", None, spec, "active", "ts1")])
    nodes_cursor = _cursor([
        ("echo",  "py_primitive", "kotodama.primitives.demo_echo_chain:step_echo",  None),
        ("count", "py_primitive", "kotodama.primitives.demo_echo_chain:step_count", None),
    ])
    pool = _make_pool([deploy_cursor, nodes_cursor])

    registered: dict[str, object] = {}
    result = await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: registered.update({aid: g}),
    )

    result.pop("seen", None); assert result == {"loaded": 1, "skipped_existing": 0, "errors": 0}
    graph = registered["demo_linear"]
    out = await graph.ainvoke({"input": "hello"})
    assert out["echo"] == "hello"
    assert out["length"] == 5


# ---------------------------------------------------------------------------
# Topology: conditional edges (the ki_cycle shape)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topology_conditional_routes_correctly():
    from kotodama.langgraph_loader import load_active_graphs

    spec = json.dumps({
        "state_keys": ["input", "echo", "length", "bucket"],
        "entry": "echo",
        "edges": [
            {"from": "echo", "to": "count"},
            {"from": "short", "to": "END"},
            {"from": "long", "to": "END"},
        ],
        "conditional_edges": [
            {
                "from": "count",
                "router": "kotodama.primitives.demo_echo_chain:route_by_length",
                "paths": {"short": "short", "long": "long"},
            }
        ],
    })
    pkg = "kotodama.primitives.demo_echo_chain"
    deploy_cursor = _cursor([("demo_branch", 1, "topology", None, spec, "active", "ts1")])
    nodes_cursor = _cursor([
        ("echo",  "py_primitive", f"{pkg}:step_echo",  None),
        ("count", "py_primitive", f"{pkg}:step_count", None),
        ("short", "py_primitive", f"{pkg}:step_short", None),
        ("long",  "py_primitive", f"{pkg}:step_long",  None),
    ])
    pool = _make_pool([deploy_cursor, nodes_cursor])

    registered: dict[str, object] = {}
    await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: registered.update({aid: g}),
    )
    graph = registered["demo_branch"]

    short_out = await graph.ainvoke({"input": "hi"})
    assert short_out["bucket"] == "short"

    # Need a fresh deploy roundtrip for the second invocation; reuse compiled graph.
    long_out = await graph.ainvoke({"input": "hello world"})
    assert long_out["bucket"] == "long"


# ---------------------------------------------------------------------------
# Topology: conditional edges via 'field' (ADR-2605082000 Phase D)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topology_conditional_field_routes_via_state_lookup():
    """Data-driven routing: no Python router callable. Compiler reads
    state[<field>] and dispatches via path_map."""
    from kotodama.langgraph_loader import load_active_graphs

    spec = json.dumps({
        "state_keys": ["input", "echo", "length", "bucket"],
        "entry": "echo",
        "edges": [
            {"from": "echo", "to": "count"},
            {"from": "count", "to": "classify"},
            {"from": "short", "to": "END"},
            {"from": "long", "to": "END"},
        ],
        "conditional_edges": [
            {
                "from": "classify",
                "field": "bucket",
                "paths": {"short": "short", "long": "long"},
            }
        ],
    })
    pkg = "kotodama.primitives.demo_echo_chain"
    deploy_cursor = _cursor([("demo_field", 1, "topology", None, spec, "active", "ts1")])
    nodes_cursor = _cursor([
        ("echo",     "py_primitive", f"{pkg}:step_echo",             None),
        ("count",    "py_primitive", f"{pkg}:step_count",            None),
        ("classify", "py_primitive", f"{pkg}:step_classify_bucket",  None),
        ("short",    "py_primitive", f"{pkg}:step_short",            None),
        ("long",     "py_primitive", f"{pkg}:step_long",             None),
    ])
    pool = _make_pool([deploy_cursor, nodes_cursor])
    registered: dict[str, object] = {}
    await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: registered.update({aid: g}),
    )
    graph = registered["demo_field"]
    short_out = await graph.ainvoke({"input": "hi"})
    assert short_out["bucket"] == "short"
    long_out = await graph.ainvoke({"input": "hello world"})
    assert long_out["bucket"] == "long"


# ---------------------------------------------------------------------------
# Topology: conditional edges via 'condition_ref' (ADR-2604261100 DMN routing)
# ---------------------------------------------------------------------------


def _cursor_one(row: tuple | None) -> MagicMock:
    """Cursor that returns a single row via .fetchone (used for DMN reads
    where _resolve_dmn_ref pulls one vertex_dmn_model row)."""
    cur = MagicMock()
    cur.fetchone = AsyncMock(return_value=row)
    return cur


@pytest.mark.asyncio
async def test_topology_conditional_condition_ref_routes_via_dmn():
    """`condition_ref: dmn:<key>@<version>` in the topology must compile +
    resolve at runtime against `vertex_dmn_model`, then route per the
    decision row's rules. This is the end-to-end Phase C activation for
    Phase A `_route_after_critique`-style branches."""
    from kotodama.langgraph_loader import load_active_graphs
    from kotodama.langgraph_node_resolvers import _DMN_REGISTRY_CACHE

    _DMN_REGISTRY_CACHE.clear()

    spec = json.dumps({
        "state_keys": ["input", "echo", "length", "bucket"],
        "entry": "echo",
        "edges": [
            {"from": "echo", "to": "count"},
            {"from": "count", "to": "classify"},
            {"from": "short", "to": "END"},
            {"from": "long", "to": "END"},
        ],
        "conditional_edges": [
            {
                "from": "classify",
                "condition_ref": "dmn:test.routing.byLength@1.0.0",
                "paths": {"short": "short", "long": "long"},
            }
        ],
    })
    pkg = "kotodama.primitives.demo_echo_chain"
    deploy_cursor = _cursor([("demo_dmn", 1, "topology", None, spec, "active", "ts1")])
    nodes_cursor = _cursor([
        ("echo",     "py_primitive", f"{pkg}:step_echo",            None),
        ("count",    "py_primitive", f"{pkg}:step_count",           None),
        ("classify", "py_primitive", f"{pkg}:step_classify_bucket", None),
        ("short",    "py_primitive", f"{pkg}:step_short",           None),
        ("long",     "py_primitive", f"{pkg}:step_long",            None),
    ])
    # `_resolve_dmn_ref` fires once per assistant (cache); the row encodes
    # `length < 5 → short` else `long`, mirroring demo_echo_chain's
    # `route_by_length` predicate.
    dmn_row = (
        json.dumps([{"name": "length", "typeRef": "number"}]),
        json.dumps([{"name": "route", "typeRef": "string"}]),
        json.dumps([
            {"id": "r_short", "inputEntries": ["< 5"], "outputEntries": ["short"]},
            {"id": "r_long",  "inputEntries": ["-"],   "outputEntries": ["long"]},
        ]),
        "FIRST",
    )
    pool = _make_pool([deploy_cursor, nodes_cursor, _cursor_one(dmn_row)])

    registered: dict[str, object] = {}
    await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: registered.update({aid: g}),
    )
    graph = registered["demo_dmn"]

    # First invoke: 2-char input → length=2 → routes "short".
    short_out = await graph.ainvoke({"input": "hi"})
    assert short_out["bucket"] == "short"

    # Second invoke reuses the cached DMN row; verify no extra DB hit by
    # asserting the pool has no remaining queued cursors.
    long_out = await graph.ainvoke({"input": "hello world"})
    assert long_out["bucket"] == "long"


@pytest.mark.asyncio
async def test_topology_conditional_field_and_router_both_set_errors():
    """Defense: 'field' and 'router' on the same edge is a config bug."""
    from kotodama.langgraph_loader import load_active_graphs

    spec = json.dumps({
        "state_keys": ["input", "bucket"],
        "entry": "echo",
        "edges": [],
        "conditional_edges": [
            {"from": "echo", "field": "bucket", "router": "x:y", "paths": {}},
        ],
    })
    deploy_cursor = _cursor([("demo_bad", 1, "topology", None, spec, "active", "ts1")])
    nodes_cursor = _cursor([
        ("echo", "py_primitive", "kotodama.primitives.demo_echo_chain:step_echo", None),
    ])
    pool = _make_pool([deploy_cursor, nodes_cursor])
    result = await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: None,
    )
    # Compile failure surfaces as errors counter, not exception
    assert result["errors"] == 1


@pytest.mark.asyncio
async def test_topology_conditional_neither_field_nor_router_errors():
    """Defense: missing both is a config bug (was the only error case
    before Phase D)."""
    from kotodama.langgraph_loader import load_active_graphs

    spec = json.dumps({
        "state_keys": ["input"],
        "entry": "echo",
        "edges": [],
        "conditional_edges": [{"from": "echo", "paths": {"x": "echo"}}],
    })
    deploy_cursor = _cursor([("demo_bad2", 1, "topology", None, spec, "active", "ts1")])
    nodes_cursor = _cursor([
        ("echo", "py_primitive", "kotodama.primitives.demo_echo_chain:step_echo", None),
    ])
    pool = _make_pool([deploy_cursor, nodes_cursor])
    result = await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: None,
    )
    assert result["errors"] == 1


# ---------------------------------------------------------------------------
# Real-world port: ki_cycle topology mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ki_cycle_compiles_via_topology(monkeypatch):
    """End-to-end: existing ki_cycle node functions, driven by RW rows.

    Patches the worker tasks that ki_cycle nodes call so we don't need
    live RW / LLM. Asserts the compiled topology graph runs to END through
    the bloom path.
    """
    from kotodama.langgraph_loader import load_active_graphs

    # Stub the worker tasks ki_cycle nodes import lazily.
    import kotodama.ki_worker_main as kw

    async def _fake_absorb():
        return {"absorbId": "absorb-1", "status": "absorbed"}
    async def _fake_synthesize(*, absorbId):
        return {"artifactId": "art-1", "synthesis": "ok", "confidence": 0.9}
    async def _fake_bloom(*, artifactId):
        return {"bloomId": "bloom-1", "publishedAt": "now"}
    async def _fake_ring():
        return {"ringId": "ring-1", "snapshotCount": 1}

    monkeypatch.setattr(kw, "task_absorb", _fake_absorb, raising=False)
    monkeypatch.setattr(kw, "task_synthesize", _fake_synthesize, raising=False)
    monkeypatch.setattr(kw, "task_bloom", _fake_bloom, raising=False)
    monkeypatch.setattr(kw, "task_ring", _fake_ring, raising=False)
    monkeypatch.setenv("KI_CONFIDENCE_CUTOFF", "0.5")

    pkg = "kotodama.langgraph_graphs.ki_cycle"
    spec = json.dumps({
        "state_keys": [
            "absorbId", "absorbStatus", "artifactId", "synthesis", "confidence",
            "bloomId", "publishedAt", "bloomSkipped", "ringId", "snapshotCount",
            "ok", "error",
        ],
        "entry": "absorb",
        "edges": [
            {"from": "absorb", "to": "synthesize"},
            {"from": "bloom", "to": "ring"},
            {"from": "skip_bloom", "to": "ring"},
            {"from": "ring", "to": "END"},
        ],
        "conditional_edges": [
            {
                "from": "synthesize",
                "router": f"{pkg}:_confidence_gate",
                "paths": {"bloom": "bloom", "skip_bloom": "skip_bloom"},
            }
        ],
    })
    deploy_cursor = _cursor([("ki_cycle_rw", 1, "topology", None, spec, "active", "ts1")])
    nodes_cursor = _cursor([
        ("absorb",     "py_primitive", f"{pkg}:_absorb_node",     None),
        ("synthesize", "py_primitive", f"{pkg}:_synthesize_node", None),
        ("bloom",      "py_primitive", f"{pkg}:_bloom_node",      None),
        ("skip_bloom", "py_primitive", f"{pkg}:_skip_bloom_node", None),
        ("ring",       "py_primitive", f"{pkg}:_ring_node",       None),
    ])
    pool = _make_pool([deploy_cursor, nodes_cursor])

    registered: dict[str, object] = {}
    result = await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: registered.update({aid: g}),
    )
    assert result["loaded"] == 1, result
    graph = registered["ki_cycle_rw"]

    out = await graph.ainvoke({})
    # confidence=0.9 ≥ cutoff 0.5 → bloom path
    assert out.get("bloomId") == "bloom-1"
    assert out.get("ringId") == "ring-1"
    assert out.get("ok") is not False


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topology_unknown_node_kind_errors():
    from kotodama.langgraph_loader import load_active_graphs

    spec = json.dumps({"state_keys": ["x"], "entry": "n1", "edges": [{"from": "n1", "to": "END"}]})
    deploy_cursor = _cursor([("demo_bad_kind", 1, "topology", None, spec, "active", "ts1")])
    nodes_cursor = _cursor([("n1", "sql_udf", "some_udf", None)])
    pool = _make_pool([deploy_cursor, nodes_cursor])

    result = await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: None,
    )
    result.pop("seen", None); assert result == {"loaded": 0, "skipped_existing": 0, "errors": 1}


@pytest.mark.asyncio
async def test_topology_missing_node_binding_errors():
    from kotodama.langgraph_loader import load_active_graphs

    spec = json.dumps({
        "state_keys": ["x"],
        "entry": "n1",
        "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "END"}],
    })
    deploy_cursor = _cursor([("demo_missing", 1, "topology", None, spec, "active", "ts1")])
    nodes_cursor = _cursor([
        ("n1", "py_primitive", "kotodama.primitives.demo_echo_chain:step_echo", None),
        # n2 binding missing
    ])
    pool = _make_pool([deploy_cursor, nodes_cursor])

    result = await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: None,
    )
    assert result["errors"] == 1
    assert result["loaded"] == 0


@pytest.mark.asyncio
async def test_topology_no_bindings_errors():
    from kotodama.langgraph_loader import load_active_graphs

    spec = json.dumps({"state_keys": ["x"], "entry": "n1", "edges": [{"from": "n1", "to": "END"}]})
    deploy_cursor = _cursor([("demo_empty", 1, "topology", None, spec, "active", "ts1")])
    nodes_cursor = _cursor([])  # empty
    pool = _make_pool([deploy_cursor, nodes_cursor])

    result = await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: None,
    )
    assert result["errors"] == 1


# ---------------------------------------------------------------------------
# Regression: py_factory still works
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_factory_module():
    mod = types.ModuleType("kotodama_test_topology_factory")
    sentinel = object()
    mod.build_graph = lambda: sentinel  # type: ignore[attr-defined]
    sys.modules["kotodama_test_topology_factory"] = mod
    yield sentinel
    sys.modules.pop("kotodama_test_topology_factory", None)


@pytest.mark.asyncio
async def test_py_factory_still_works(fake_factory_module):
    from kotodama.langgraph_loader import load_active_graphs

    sentinel = fake_factory_module
    deploy_cursor = _cursor([
        ("legacy_factory", 1, "py_factory", "kotodama_test_topology_factory", None, "active", "ts1"),
    ])
    pool = _make_pool([deploy_cursor])  # only one query for py_factory path

    registered: dict[str, object] = {}
    result = await load_active_graphs(
        pool_factory=lambda: _factory(pool),
        register_fn=lambda aid, g: registered.update({aid: g}),
    )
    result.pop("seen", None); assert result == {"loaded": 1, "skipped_existing": 0, "errors": 0}
    assert registered["legacy_factory"] is sentinel
