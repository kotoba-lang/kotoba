"""Tests for the DMN condition router + vision LLM resolver
(P10.1b / P10.3b of ADR-2605141200).

`make_dmn_condition_router` evaluates a `vertex_dmn_model` row at runtime
so topology `conditional_edges[].condition_ref = dmn:<key>@<version>` can
flip routing without code changes. `make_llm_vision_node` resolves an
``image_keys`` dotted-path list against state, fetches blobs via a
caller-supplied `blob_fetcher`, base64-encodes them, and posts the bundle
through `kotodama.llm.call_tier_vision_json`.

All tests are pure-CPU — psycopg pool + vision HTTP are mocked.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _async_return(value):
    async def _coro():
        return value
    return _coro


def _pool_returning(row: tuple | None):
    cur = MagicMock()
    cur.fetchone = AsyncMock(return_value=row)
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=cur)

    @asynccontextmanager
    async def _cm():
        yield conn

    pool = MagicMock()
    pool.connection = _cm
    return pool, conn


_REFINEMENT_ROW = (
    json.dumps([
        {"name": "score", "typeRef": "number"},
        {"name": "iteration", "typeRef": "number"},
        {"name": "maxIter", "typeRef": "number"},
    ]),
    json.dumps([
        {"name": "route", "typeRef": "string"},
        {"name": "reason", "typeRef": "string"},
    ]),
    json.dumps([
        {
            "id": "RefinementRule_refine",
            "inputEntries": ["< 0.75", "< maxIter", "-"],
            "outputEntries": ["cinematography", "score-below-acceptance-bar"],
        },
        {
            "id": "RefinementRule_persist",
            "inputEntries": ["-", "-", "-"],
            "outputEntries": ["persist", "accept-or-budget-exhausted"],
        },
    ]),
    "FIRST",
)


# ---------------------------------------------------------------------------
# _parse_dmn_ref
# ---------------------------------------------------------------------------


def test_parse_dmn_ref_strips_version_suffix():
    from kotodama.langgraph_node_resolvers import _parse_dmn_ref

    assert _parse_dmn_ref("dmn:com.etzhayyim.policies.foo.bar@1.0.0") == (
        "com.etzhayyim.policies.foo.bar", 1,
    )
    assert _parse_dmn_ref("dmn:foo@2") == ("foo", 2)
    # No version → default to 1.
    assert _parse_dmn_ref("dmn:foo") == ("foo", 1)


def test_parse_dmn_ref_rejects_non_dmn_scheme():
    from kotodama.langgraph_node_resolvers import _parse_dmn_ref

    with pytest.raises(ValueError, match="must start with"):
        _parse_dmn_ref("rego://foo")


def test_parse_dmn_ref_rejects_non_integer_major():
    from kotodama.langgraph_node_resolvers import _parse_dmn_ref

    with pytest.raises(ValueError, match="integer-major"):
        _parse_dmn_ref("dmn:foo@vNext")


# ---------------------------------------------------------------------------
# _eval_dmn_input_entry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry,value,state,expected",
    [
        # Don't-care wildcard.
        ("-", 0.5, {}, True),
        ("-", None, {}, True),
        ("", "anything", {}, True),
        (None, 0, {}, True),
        # Numeric literal comparisons.
        ("< 0.75", 0.5, {}, True),
        ("< 0.75", 0.75, {}, False),
        ("< 0.75", 0.9, {}, False),
        ("<= 0.75", 0.75, {}, True),
        ("> 0.75", 0.9, {}, True),
        ("> 0.75", 0.75, {}, False),
        (">= 0.75", 0.75, {}, True),
        # Named-ref comparisons (resolved against `state`).
        ("< maxIter", 2, {"maxIter": 3}, True),
        ("< maxIter", 3, {"maxIter": 3}, False),
        ("<= maxIter", 3, {"maxIter": 3}, True),
        # Equality (== + bare literal forms).
        ("== 5", 5, {}, True),
        ("== 5", 4, {}, False),
        ('"red"', "red", {}, True),
        ('"red"', "blue", {}, False),
        ("5", 5, {}, True),
        ("5", 4, {}, False),
        # Non-numeric input on a numeric predicate → false (don't silently match).
        ("< 0.75", "not a number", {}, False),
        ("< 0.75", None, {}, False),
    ],
)
def test_eval_dmn_input_entry_matrix(entry, value, state, expected):
    from kotodama.langgraph_node_resolvers import _eval_dmn_input_entry

    assert _eval_dmn_input_entry(entry, value, state) is expected


# ---------------------------------------------------------------------------
# _eval_dmn_rule (AND semantics)
# ---------------------------------------------------------------------------


def test_eval_dmn_rule_all_inputs_must_match():
    from kotodama.langgraph_node_resolvers import _eval_dmn_rule

    inputs_meta = [
        {"name": "score"},
        {"name": "iteration"},
        {"name": "maxIter"},
    ]
    rule = {
        "id": "refine",
        "inputEntries": ["< 0.75", "< maxIter", "-"],
        "outputEntries": ["cinematography"],
    }
    # All match.
    assert _eval_dmn_rule(rule, inputs_meta, {"score": 0.5, "iteration": 1, "maxIter": 3}) is True
    # score fails.
    assert _eval_dmn_rule(rule, inputs_meta, {"score": 0.9, "iteration": 1, "maxIter": 3}) is False
    # iteration budget exhausted.
    assert _eval_dmn_rule(rule, inputs_meta, {"score": 0.5, "iteration": 3, "maxIter": 3}) is False


# ---------------------------------------------------------------------------
# _resolve_dmn_ref (cache + DB shape)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_dmn_ref_caches_after_first_hit():
    from kotodama.langgraph_node_resolvers import (
        _DMN_REGISTRY_CACHE, _resolve_dmn_ref,
    )

    _DMN_REGISTRY_CACHE.clear()
    pool, conn = _pool_returning(_REFINEMENT_ROW)
    ref = "dmn:com.etzhayyim.policies.mangaka.composeScene3dRefinement@1.0.0"

    out1 = await _resolve_dmn_ref(ref, lambda: _async_return(pool)())
    out2 = await _resolve_dmn_ref(ref, lambda: _async_return(pool)())

    assert out1["decision_key"] == "com.etzhayyim.policies.mangaka.composeScene3dRefinement"
    assert out1["version"] == 1
    assert out1["hit_policy"] == "FIRST"
    assert len(out1["inputs"]) == 3
    assert len(out1["rules"]) == 2
    # Cache hit on second call — execute should fire only once.
    assert conn.execute.await_count == 1
    assert out1 is out2


@pytest.mark.asyncio
async def test_resolve_dmn_ref_raises_on_missing_row():
    from kotodama.langgraph_node_resolvers import (
        _DMN_REGISTRY_CACHE, _resolve_dmn_ref,
    )

    _DMN_REGISTRY_CACHE.clear()
    pool, _ = _pool_returning(None)

    with pytest.raises(ValueError, match="no active row"):
        await _resolve_dmn_ref(
            "dmn:does.not.exist@1", lambda: _async_return(pool)(),
        )


# ---------------------------------------------------------------------------
# make_dmn_condition_router
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "score,iteration,max_iter,expected",
    [
        # Same matrix as test_compose_scene_3d_refinement_dmn.py.
        (0.0, 0, 3, "cinematography"),
        (0.5, 1, 3, "cinematography"),
        (0.7499, 2, 3, "cinematography"),
        (0.75, 0, 3, "persist"),
        (0.9, 0, 3, "persist"),
        (1.0, 0, 3, "persist"),
        (0.0, 3, 3, "persist"),
        (0.0, 4, 3, "persist"),
        (0.95, 5, 3, "persist"),
    ],
)
async def test_dmn_router_matches_python_route_after_critique(
    score, iteration, max_iter, expected,
):
    from kotodama.langgraph_node_resolvers import (
        _DMN_REGISTRY_CACHE, make_dmn_condition_router,
    )

    _DMN_REGISTRY_CACHE.clear()
    pool, _ = _pool_returning(_REFINEMENT_ROW)
    router = make_dmn_condition_router(
        "dmn:com.etzhayyim.policies.mangaka.composeScene3dRefinement@1.0.0",
        lambda: _async_return(pool)(),
    )

    route = await router({"score": score, "iteration": iteration, "maxIter": max_iter})
    assert route == expected


@pytest.mark.asyncio
async def test_dmn_router_strips_quoted_output_literals():
    """Some DMN seeds wrap outputEntries in literal quotes (\"persist\");
    the router must strip them so they match `paths` keys."""
    from kotodama.langgraph_node_resolvers import (
        _DMN_REGISTRY_CACHE, make_dmn_condition_router,
    )

    _DMN_REGISTRY_CACHE.clear()
    row = (
        json.dumps([{"name": "x"}]),
        json.dumps([{"name": "route"}]),
        json.dumps([
            {"id": "r1", "inputEntries": ["-"], "outputEntries": ['"persist"']},
        ]),
        "FIRST",
    )
    pool, _ = _pool_returning(row)
    router = make_dmn_condition_router(
        "dmn:test.policy@1", lambda: _async_return(pool)(),
    )
    assert await router({"x": 0}) == "persist"


@pytest.mark.asyncio
async def test_dmn_router_requires_pool_factory():
    from kotodama.langgraph_node_resolvers import make_dmn_condition_router

    with pytest.raises(ValueError, match="pool_factory"):
        make_dmn_condition_router("dmn:foo@1", None)


@pytest.mark.asyncio
async def test_dmn_router_rejects_non_first_hit_policy():
    from kotodama.langgraph_node_resolvers import (
        _DMN_REGISTRY_CACHE, make_dmn_condition_router,
    )

    _DMN_REGISTRY_CACHE.clear()
    row = (
        json.dumps([{"name": "x"}]),
        json.dumps([{"name": "route"}]),
        json.dumps([{"id": "r1", "inputEntries": ["-"], "outputEntries": ["x"]}]),
        "PRIORITY",
    )
    pool, _ = _pool_returning(row)
    router = make_dmn_condition_router(
        "dmn:test.policy@1", lambda: _async_return(pool)(),
    )
    with pytest.raises(NotImplementedError, match="PRIORITY"):
        await router({"x": 0})


@pytest.mark.asyncio
async def test_dmn_router_raises_when_no_rule_matches():
    from kotodama.langgraph_node_resolvers import (
        _DMN_REGISTRY_CACHE, make_dmn_condition_router,
    )

    _DMN_REGISTRY_CACHE.clear()
    # Single rule that requires score > 100 — nothing in normal state matches.
    row = (
        json.dumps([{"name": "score"}]),
        json.dumps([{"name": "route"}]),
        json.dumps([
            {"id": "r1", "inputEntries": ["> 100"], "outputEntries": ["unreachable"]},
        ]),
        "FIRST",
    )
    pool, _ = _pool_returning(row)
    router = make_dmn_condition_router(
        "dmn:test.policy@1", lambda: _async_return(pool)(),
    )
    with pytest.raises(ValueError, match="no rule matched"):
        await router({"score": 0.5})


# ---------------------------------------------------------------------------
# make_llm_vision_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_vision_node_resolves_single_image_path():
    from kotodama.langgraph_node_resolvers import make_llm_vision_node

    fetched: list[str] = []

    async def fake_blob_fetcher(key: str) -> bytes:
        fetched.append(key)
        return b"\x89PNG-fake-bytes"

    cfg = {
        "input_keys": ["panel_plan"],
        "image_keys": ["selected.blobKey"],
        "result_key": "critique_raw",
        "args": {
            "system": "system prompt",
            "user_template": "Panel: {panel_plan}",
            "max_tokens": 64,
            "temperature": 0.1,
        },
    }
    node = make_llm_vision_node("vision", cfg, blob_fetcher=fake_blob_fetcher)

    captured: dict = {}

    def fake_vision(tier, system, user, images_b64, **kw):
        captured.update(
            tier=tier, system=system, user=user,
            images_b64=images_b64, kw=kw,
        )
        return {"ok": True, "data": {"score": 0.8}}

    with patch("kotodama.llm.call_tier_vision_json", fake_vision):
        out = await node({
            "panel_plan": {"shot": "Closeup"},
            "selected": {"blobKey": "blobs/anon/aaa"},
        })

    assert fetched == ["blobs/anon/aaa"]
    assert captured["tier"] == "vision"
    assert captured["system"] == "system prompt"
    assert "Panel:" in captured["user"]
    # Base64 of the fake bytes.
    import base64
    assert captured["images_b64"] == [base64.b64encode(b"\x89PNG-fake-bytes").decode("ascii")]
    assert captured["kw"]["max_tokens"] == 64
    assert captured["kw"]["temperature"] == pytest.approx(0.1)
    assert out == {"critique_raw": {"ok": True, "data": {"score": 0.8}}}


@pytest.mark.asyncio
async def test_llm_vision_node_walks_array_path_for_many_images():
    from kotodama.langgraph_node_resolvers import make_llm_vision_node

    fetched: list[str] = []

    async def fake_blob_fetcher(key: str) -> bytes:
        fetched.append(key)
        return key.encode("utf-8")  # distinct payloads per blob

    cfg = {
        "input_keys": [],
        "image_keys": ["renders.*.blobKey"],
        "result_key": "critique",
        "args": {"system": "s", "user_template": ""},
    }
    node = make_llm_vision_node("vision", cfg, blob_fetcher=fake_blob_fetcher)

    state = {
        "renders": [
            {"blobKey": "blobs/anon/a", "angle": "FullShot"},
            {"blobKey": "blobs/anon/b", "angle": "Closeup"},
            {"blobKey": "blobs/anon/c", "angle": "OverShoulder"},
        ],
    }

    with patch("kotodama.llm.call_tier_vision_json", lambda *a, **k: {"ok": True}):
        await node(state)

    assert fetched == ["blobs/anon/a", "blobs/anon/b", "blobs/anon/c"]


@pytest.mark.asyncio
async def test_llm_vision_node_skips_missing_blobs():
    """`blob_fetcher` returning None for a key must drop that image rather
    than crash — vision call still runs with the others."""
    from kotodama.langgraph_node_resolvers import make_llm_vision_node

    async def fake_blob_fetcher(key: str):
        return None if key.endswith("missing") else b"ok"

    cfg = {
        "input_keys": [],
        "image_keys": ["renders.*.blobKey"],
        "result_key": "critique",
        "args": {"system": "s", "user_template": ""},
    }
    node = make_llm_vision_node("vision", cfg, blob_fetcher=fake_blob_fetcher)

    seen_lens: list[int] = []

    def fake_vision(tier, system, user, images_b64, **kw):
        seen_lens.append(len(images_b64))
        return {"ok": True}

    with patch("kotodama.llm.call_tier_vision_json", fake_vision):
        await node({
            "renders": [
                {"blobKey": "blobs/anon/a"},
                {"blobKey": "blobs/anon/missing"},
                {"blobKey": "blobs/anon/c"},
            ],
        })

    # 2 valid blobs → 2 base64 strings.
    assert seen_lens == [2]


@pytest.mark.asyncio
async def test_llm_vision_node_requires_blob_fetcher_when_image_keys_set():
    from kotodama.langgraph_node_resolvers import make_llm_vision_node

    cfg = {
        "input_keys": [],
        "image_keys": ["selected.blobKey"],
        "result_key": "critique",
        "args": {},
    }
    with pytest.raises(ValueError, match="blob_fetcher is required"):
        make_llm_vision_node("vision", cfg, blob_fetcher=None)


@pytest.mark.asyncio
async def test_llm_vision_node_requires_result_key():
    from kotodama.langgraph_node_resolvers import make_llm_vision_node

    with pytest.raises(ValueError, match="result_key"):
        make_llm_vision_node(
            "vision",
            {"input_keys": [], "image_keys": [], "args": {}},
            blob_fetcher=None,
        )


# ---------------------------------------------------------------------------
# MCP_NSID_OVERRIDE_*  (P9 blocker #4 — in-cluster short-circuit)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_nsid_override_short_circuits_db_lookup(monkeypatch):
    """`MCP_NSID_OVERRIDE_<prefix>=<base_url>` env var lets a pod point
    intra-pod MCP calls at localhost without touching `vertex_mcp_tool_def`.
    The DB layer must not be hit when the override matches."""
    from kotodama.langgraph_node_resolvers import (
        _MCP_REGISTRY_CACHE, _resolve_mcp_nsid,
    )

    _MCP_REGISTRY_CACHE.clear()
    monkeypatch.setenv(
        "MCP_NSID_OVERRIDE_ai_etzhayyim_apps_mangaka_tools", "http://localhost:8000",
    )

    # A pool that would raise if accessed — proves the override bypasses it.
    async def _explode_pool():
        raise AssertionError("DB lookup must not fire when override matches")

    url = await _resolve_mcp_nsid(
        "com.etzhayyim.apps.mangaka.tools.loadPanelPlan", _explode_pool,
    )
    assert url == "http://localhost:8000/xrpc/com.etzhayyim.mcp.message"


@pytest.mark.asyncio
async def test_mcp_nsid_override_longest_prefix_wins(monkeypatch):
    from kotodama.langgraph_node_resolvers import (
        _MCP_REGISTRY_CACHE, _resolve_mcp_nsid,
    )

    _MCP_REGISTRY_CACHE.clear()
    monkeypatch.setenv("MCP_NSID_OVERRIDE_ai_etzhayyim_apps", "http://broad:80")
    monkeypatch.setenv(
        "MCP_NSID_OVERRIDE_ai_etzhayyim_apps_mangaka_tools", "http://specific:9000",
    )

    async def _unused_pool():
        return None

    url = await _resolve_mcp_nsid(
        "com.etzhayyim.apps.mangaka.tools.loadPanelPlan", _unused_pool,
    )
    assert url.startswith("http://specific:9000")


@pytest.mark.asyncio
async def test_mcp_nsid_override_does_not_match_prefix_substring(monkeypatch):
    """`com.etzhayyim.appsXYZ.tools.foo` must NOT match the
    `com.etzhayyim.apps` prefix — only exact segment boundaries count."""
    from kotodama.langgraph_node_resolvers import (
        _MCP_REGISTRY_CACHE, _resolve_mcp_nsid,
    )

    _MCP_REGISTRY_CACHE.clear()
    monkeypatch.setenv("MCP_NSID_OVERRIDE_ai_etzhayyim_apps_mangaka", "http://nope:80")

    pool, conn = _pool_returning(("real-host.etzhayyim.com",))
    url = await _resolve_mcp_nsid(
        "com.etzhayyim.apps.mangakatv.something",  # `mangakatv` ≠ `mangaka` segment
        lambda: _async_return(pool)(),
    )
    # Override should NOT match (prefix segment mismatch) → DB path used.
    assert "real-host.etzhayyim.com" in url
    assert conn.execute.await_count == 1


@pytest.mark.asyncio
async def test_mcp_nsid_no_override_falls_back_to_db(monkeypatch):
    """When no override env var matches, `_resolve_mcp_nsid` reverts to
    its existing `vertex_mcp_tool_def` lookup path."""
    from kotodama.langgraph_node_resolvers import (
        _MCP_REGISTRY_CACHE, _resolve_mcp_nsid,
    )

    _MCP_REGISTRY_CACHE.clear()
    # Strip any inherited overrides so the env is clean.
    for k in list(os.environ):
        if k.startswith("MCP_NSID_OVERRIDE_"):
            monkeypatch.delenv(k, raising=False)

    pool, conn = _pool_returning(("foo.etzhayyim.com",))
    url = await _resolve_mcp_nsid(
        "com.etzhayyim.apps.someApp.tools.do", lambda: _async_return(pool)(),
    )
    assert url == "https://foo.etzhayyim.com/xrpc/com.etzhayyim.mcp.message"
    assert conn.execute.await_count == 1


@pytest.mark.asyncio
async def test_mcp_nsid_override_matches_exact_nsid(monkeypatch):
    """When the override key equals the full NSID (no trailing segments),
    the override still fires."""
    from kotodama.langgraph_node_resolvers import (
        _MCP_REGISTRY_CACHE, _resolve_mcp_nsid,
    )

    _MCP_REGISTRY_CACHE.clear()
    monkeypatch.setenv(
        "MCP_NSID_OVERRIDE_ai_etzhayyim_apps_mangaka_tools_loadPanelPlan",
        "http://exact:7000",
    )

    async def _unused_pool():
        return None

    url = await _resolve_mcp_nsid(
        "com.etzhayyim.apps.mangaka.tools.loadPanelPlan", _unused_pool,
    )
    assert url == "http://exact:7000/xrpc/com.etzhayyim.mcp.message"


@pytest.mark.asyncio
async def test_llm_vision_dispatched_via_resolve_node():
    """Confirm the kind="llm_vision" dispatch path in resolve_node hands off
    to make_llm_vision_node with the blob_fetcher kwarg."""
    from kotodama.langgraph_node_resolvers import resolve_node

    async def fake_blob_fetcher(key: str) -> bytes:
        return b"png"

    cfg = {
        "input_keys": [],
        "image_keys": ["selected.blobKey"],
        "result_key": "x",
        "args": {"system": "s", "user_template": ""},
    }
    node = resolve_node(
        "llm_vision", "vision", cfg, blob_fetcher=fake_blob_fetcher,
    )
    with patch("kotodama.llm.call_tier_vision_json",
               lambda *a, **k: {"ok": True, "data": {"y": 1}}):
        out = await node({"selected": {"blobKey": "blobs/anon/a"}})
    assert out == {"x": {"ok": True, "data": {"y": 1}}}
