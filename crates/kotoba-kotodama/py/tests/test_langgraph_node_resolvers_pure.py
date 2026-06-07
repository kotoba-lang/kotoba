"""Tests for langgraph_node_resolvers (P1b — sql_udf / py_ext_udf / mcp_tool / llm)."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# sql_udf / py_ext_udf
# ---------------------------------------------------------------------------


def _pool_returning(row: tuple):
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


@pytest.mark.asyncio
async def test_sql_udf_node_executes_and_returns_result_key():
    from kotodama.langgraph_node_resolvers import make_sql_udf_node

    pool, conn = _pool_returning((42,))
    cfg = {"input_keys": ["a", "b"], "result_key": "score"}
    node = make_sql_udf_node("classify_t1", cfg, lambda: _async_return(pool))

    out = await node({"a": "hello", "b": "world", "ignored": "x"})

    assert out == {"score": 42}
    # Verify SQL shape and params
    args, kwargs = conn.execute.call_args
    assert args[0] == "SELECT classify_t1(%s, %s)"
    assert args[1] == ("hello", "world")
    assert kwargs.get("prepare") is False


@pytest.mark.asyncio
async def test_sql_udf_via_resolve_node_dispatch():
    from kotodama.langgraph_node_resolvers import resolve_node

    pool, _conn = _pool_returning((1,))
    cfg_json = json.dumps({"input_keys": ["x"], "result_key": "y"})
    node = resolve_node("sql_udf", "fn", cfg_json, pool_factory=lambda: _async_return(pool))
    out = await node({"x": 7})
    assert out == {"y": 1}


@pytest.mark.asyncio
async def test_py_ext_udf_uses_same_path_as_sql_udf():
    from kotodama.langgraph_node_resolvers import resolve_node

    pool, conn = _pool_returning(("ok",))
    cfg = {"input_keys": ["url"], "result_key": "fetched"}
    node = resolve_node("py_ext_udf", "url_fetch_score", cfg, pool_factory=lambda: _async_return(pool))
    out = await node({"url": "http://x"})
    assert out == {"fetched": "ok"}
    assert conn.execute.call_args.args[0] == "SELECT url_fetch_score(%s)"


def test_sql_udf_missing_result_key_errors():
    from kotodama.langgraph_node_resolvers import make_sql_udf_node
    with pytest.raises(ValueError, match="result_key"):
        make_sql_udf_node("fn", {"input_keys": ["a"]}, pool_factory=lambda: None)


# ---------------------------------------------------------------------------
# mcp_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_tool_node_posts_envelope():
    from kotodama.langgraph_node_resolvers import make_mcp_tool_node

    cfg = {
        "input_keys": ["query", "limit"],
        "result_key": "research",
        "args": {"name": "web_research", "headers": {"x-test": "1"}},
    }
    node = make_mcp_tool_node("https://mcp.etzhayyim.com/xrpc/com.etzhayyim.mcp.message", cfg)

    sent = {}

    class _FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"ok": True, "result": [1, 2, 3]}

    class _FakeClient:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def post(self, url, json=None, headers=None):
            sent["url"] = url
            sent["json"] = json
            sent["headers"] = headers
            return _FakeResponse()

    with patch("httpx.AsyncClient", _FakeClient):
        out = await node({"query": "RW commit", "limit": 5})

    assert out == {"research": {"ok": True, "result": [1, 2, 3]}}
    assert sent["url"].endswith("/com.etzhayyim.mcp.message")
    assert sent["json"] == {
        "method": "tools/call",
        "params": {
            "name": "web_research",
            "arguments": {"query": "RW commit", "limit": 5},
        },
    }
    assert sent["headers"]["x-test"] == "1"
    assert sent["headers"]["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_mcp_tool_static_args_merged_into_arguments():
    """ADR-2605082000 §2.6 follow-up — config.args.* (other than name/headers)
    flow into the envelope's arguments as static defaults. State `input_keys`
    override on key collision, so identity nodes (input_keys=[]) work."""
    from kotodama.langgraph_node_resolvers import make_mcp_tool_node

    cfg = {
        "input_keys": [],
        "result_key": "out",
        "args": {
            "name": "com.etzhayyim.tools.const.echo",
            "constant": {"bloomSkipped": True, "bloomId": None},
        },
    }
    node = make_mcp_tool_node("https://x.example/xrpc/com.etzhayyim.mcp.message", cfg)

    sent: dict = {}

    class _R:
        def raise_for_status(self): pass
        def json(self): return {"bloomSkipped": True, "bloomId": None}

    class _C:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def post(self, url, json=None, headers=None):
            sent["json"] = json
            return _R()

    with patch("httpx.AsyncClient", _C):
        result = await node({"any": "state"})

    assert result == {"out": {"bloomSkipped": True, "bloomId": None}}
    # static args reach the wire; reserved keys (name) are NOT duplicated.
    assert sent["json"]["params"]["name"] == "com.etzhayyim.tools.const.echo"
    assert sent["json"]["params"]["arguments"] == {
        "constant": {"bloomSkipped": True, "bloomId": None}
    }


@pytest.mark.asyncio
async def test_mcp_tool_input_paths_navigates_nested_state():
    """ADR-2605082000 §2.6 follow-up — input_paths walks nested state via
    the json.extract grammar. Bridges http.fetch → downstream nodes that
    need a sub-tree (e.g. Crossref message.items[0].DOI)."""
    from kotodama.langgraph_node_resolvers import make_mcp_tool_node

    cfg = {
        "input_keys": [],
        "input_paths": {
            "json": "fetchOut.body",
            "first_doi": "fetchOut.body.message.items[0].DOI",
        },
        "result_key": "out",
        "args": {"name": "com.etzhayyim.tools.json.extract", "path": "message.items"},
    }
    node = make_mcp_tool_node("https://x.example/xrpc/com.etzhayyim.mcp.message", cfg)

    sent: dict = {}

    class _R:
        def raise_for_status(self): pass
        def json(self): return {"value": [{"DOI": "10.1/abc"}]}

    class _C:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def post(self, url, json=None, headers=None):
            sent["json"] = json
            return _R()

    state = {
        "fetchOut": {
            "body": {
                "message": {"items": [{"DOI": "10.1/abc"}, {"DOI": "10.2/def"}]},
            },
        },
    }
    with patch("httpx.AsyncClient", _C):
        await node(state)

    args = sent["json"]["params"]["arguments"]
    assert args["json"] == state["fetchOut"]["body"]
    assert args["first_doi"] == "10.1/abc"
    # static args still pass through
    assert args["path"] == "message.items"


def test_mcp_tool_requires_name():
    from kotodama.langgraph_node_resolvers import make_mcp_tool_node
    with pytest.raises(ValueError, match="name required"):
        make_mcp_tool_node("https://x", {"input_keys": ["q"], "result_key": "r"})


def test_mcp_tool_registry_ref_requires_pool_factory():
    """ADR-2605082000 §2.6 — mcp://<nsid> needs pool_factory for resolution."""
    from kotodama.langgraph_node_resolvers import make_mcp_tool_node
    with pytest.raises(ValueError, match="pool_factory required"):
        make_mcp_tool_node(
            "mcp://com.etzhayyim.tools.web.research",
            {"input_keys": ["q"], "result_key": "r"},
        )


def test_mcp_tool_registry_ref_empty_nsid_rejected():
    from kotodama.langgraph_node_resolvers import make_mcp_tool_node
    with pytest.raises(ValueError, match="nsid is empty"):
        make_mcp_tool_node(
            "mcp://",
            {"input_keys": ["q"], "result_key": "r"},
            pool_factory=lambda: _async_return(None),
        )


@pytest.mark.asyncio
async def test_mcp_tool_registry_ref_resolves_via_vertex_mcp_tool_def():
    """ADR-2605082000 §2.6 — mcp://<nsid> resolves to https://{actor_host}/xrpc/...
    via SELECT on vertex_mcp_tool_def, defaulting tools/call name to nsid.
    Cache hit on the second invocation skips the SELECT."""
    from kotodama import langgraph_node_resolvers as mod

    # Reset cache so the test is hermetic.
    mod._MCP_REGISTRY_CACHE.clear()

    pool, conn = _pool_returning(("research.etzhayyim.com",))
    cfg = {"input_keys": ["query"], "result_key": "out"}
    node = mod.make_mcp_tool_node(
        "mcp://com.etzhayyim.tools.web.research",
        cfg,
        pool_factory=lambda: _async_return(pool),
    )

    sent: dict = {}

    class _FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"ok": True}

    class _FakeClient:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def post(self, url, json=None, headers=None):
            sent.setdefault("urls", []).append(url)
            sent.setdefault("envelopes", []).append(json)
            return _FakeResponse()

    with patch("httpx.AsyncClient", _FakeClient):
        out1 = await node({"query": "RW"})
        out2 = await node({"query": "RW2"})

    assert out1 == {"out": {"ok": True}}
    assert out2 == {"out": {"ok": True}}
    # Endpoint built from registry actor_host:
    assert sent["urls"] == [
        "https://research.etzhayyim.com/xrpc/com.etzhayyim.mcp.message",
        "https://research.etzhayyim.com/xrpc/com.etzhayyim.mcp.message",
    ]
    # tools/call name defaults to the nsid:
    assert sent["envelopes"][0]["params"]["name"] == "com.etzhayyim.tools.web.research"
    # Registry SELECT happened exactly once thanks to TTL cache.
    assert conn.execute.await_count == 1


# ---------------------------------------------------------------------------
# llm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_node_calls_call_tier_json():
    from kotodama.langgraph_node_resolvers import make_llm_node

    cfg = {
        "input_keys": ["question"],
        "result_key": "answer",
        "args": {
            "system": "You are concise.",
            "user_template": "Q: {question}",
            "max_tokens": 200,
            "temperature": 0.0,
        },
    }
    node = make_llm_node("structured", cfg)

    captured = {}
    def _fake_call_tier_json(tier, system, user, *, max_tokens, temperature):
        captured["tier"] = tier
        captured["system"] = system
        captured["user"] = user
        captured["max_tokens"] = max_tokens
        captured["temperature"] = temperature
        return {"verdict": "yes"}

    with patch("kotodama.llm.call_tier_json", _fake_call_tier_json):
        out = await node({"question": "Is RW running?"})

    assert out == {"answer": {"verdict": "yes"}}
    assert captured["tier"] == "structured"
    assert captured["user"] == "Q: Is RW running?"
    assert captured["max_tokens"] == 200
    assert captured["temperature"] == 0.0


@pytest.mark.asyncio
async def test_llm_node_template_format_failure_falls_back_to_raw():
    from kotodama.langgraph_node_resolvers import make_llm_node

    cfg = {
        "input_keys": ["a"],
        "result_key": "out",
        "args": {"user_template": "Hello {missing}"},  # KeyError on format
    }
    node = make_llm_node("general", cfg)
    captured = {}
    def _fake(tier, system, user, **_):
        captured["user"] = user
        return {}
    with patch("kotodama.llm.call_tier_json", _fake):
        await node({"a": "x"})
    # On format failure, raw template is sent
    assert captured["user"] == "Hello {missing}"


# ---------------------------------------------------------------------------
# unknown kind
# ---------------------------------------------------------------------------


def test_resolve_node_unknown_kind_raises():
    from kotodama.langgraph_node_resolvers import resolve_node
    with pytest.raises(NotImplementedError, match="future_kind"):
        resolve_node("future_kind", "ref", None)


def test_sql_udf_requires_pool_factory():
    from kotodama.langgraph_node_resolvers import resolve_node
    with pytest.raises(ValueError, match="pool_factory"):
        resolve_node("sql_udf", "fn", {"input_keys": [], "result_key": "x"})


# ---------------------------------------------------------------------------
# foreach (ADR-2605082000 Phase D — topology operator)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_foreach_iterates_inner_node_over_items():
    """Resolves items_path → list, runs inner LLM node per item, collects
    outputs in result_key. Default item_key='item'."""
    from kotodama.langgraph_node_resolvers import make_foreach_node

    cfg = {
        "items_path": "writes",
        "result_key": "out",
        "node": {
            "kind": "llm",
            "ref": "structured",
            "config": {
                "input_keys": ["item"],
                "result_key": "_unused",
                "args": {"system": "s", "user_template": "{item}"},
            },
        },
    }
    node = make_foreach_node(cfg)

    # Stub the LLM call so the inner node returns the item it received.
    with patch("kotodama.llm.call_tier_json", side_effect=lambda *a, **kw: {"echoed": a[2]}):
        out = await node({"writes": [{"k": 1}, {"k": 2}, {"k": 3}]})

    assert "out" in out and len(out["out"]) == 3
    # inner llm node returns dict like {"_unused": <result>}
    for sub in out["out"]:
        assert "_unused" in sub


@pytest.mark.asyncio
async def test_foreach_via_resolve_node_dispatch():
    """resolve_node('foreach', ...) wires through the same path as direct
    make_foreach_node. Uses transform.map proxy to avoid LLM stub."""
    from kotodama.langgraph_node_resolvers import resolve_node

    inner_kind = "llm"
    cfg = {
        "items_path": "items",
        "result_key": "results",
        "item_key": "current",
        "node": {
            "kind": inner_kind,
            "ref": "structured",
            "config": {
                "input_keys": ["current"],
                "result_key": "_r",
                "args": {"system": "", "user_template": "x"},
            },
        },
    }
    node = resolve_node("foreach", "", cfg)
    with patch("kotodama.llm.call_tier_json", return_value={"ok": True}):
        out = await node({"items": ["a", "b"]})
    assert out == {"results": [{"_r": {"ok": True}}, {"_r": {"ok": True}}]}


@pytest.mark.asyncio
async def test_foreach_empty_list_returns_empty_results():
    from kotodama.langgraph_node_resolvers import make_foreach_node
    node = make_foreach_node({
        "items_path": "writes",
        "result_key": "out",
        "node": {"kind": "llm", "ref": "t",
                 "config": {"input_keys": [], "result_key": "_r",
                            "args": {"system": "", "user_template": ""}}},
    })
    out = await node({"writes": []})
    assert out == {"out": []}


@pytest.mark.asyncio
async def test_foreach_missing_items_path_returns_empty():
    """Path resolves to None (key missing) → empty list, no error."""
    from kotodama.langgraph_node_resolvers import make_foreach_node
    node = make_foreach_node({
        "items_path": "absent.deep.path",
        "result_key": "out",
        "node": {"kind": "llm", "ref": "t",
                 "config": {"input_keys": [], "result_key": "_r",
                            "args": {"system": "", "user_template": ""}}},
    })
    out = await node({"writes": [1]})
    assert out == {"out": []}


@pytest.mark.asyncio
async def test_foreach_non_list_items_emits_error():
    from kotodama.langgraph_node_resolvers import make_foreach_node
    node = make_foreach_node({
        "items_path": "data",
        "result_key": "out",
        "node": {"kind": "llm", "ref": "t",
                 "config": {"input_keys": [], "result_key": "_r",
                            "args": {"system": "", "user_template": ""}}},
    })
    out = await node({"data": {"not": "a list"}})
    assert out["out"] == []
    assert "__foreach_error" in out


def test_foreach_missing_items_path_config_raises():
    from kotodama.langgraph_node_resolvers import make_foreach_node
    with pytest.raises(ValueError, match="items_path"):
        make_foreach_node({"result_key": "x", "node": {"kind": "llm", "ref": "t"}})


def test_foreach_missing_result_key_config_raises():
    from kotodama.langgraph_node_resolvers import make_foreach_node
    with pytest.raises(ValueError, match="result_key"):
        make_foreach_node({"items_path": "x", "node": {"kind": "llm", "ref": "t"}})


def test_foreach_missing_inner_node_raises():
    from kotodama.langgraph_node_resolvers import make_foreach_node
    with pytest.raises(ValueError, match="config.node"):
        make_foreach_node({"items_path": "x", "result_key": "y"})


def test_foreach_inner_unknown_kind_raises():
    from kotodama.langgraph_node_resolvers import make_foreach_node
    with pytest.raises(NotImplementedError):
        make_foreach_node({
            "items_path": "x", "result_key": "y",
            "node": {"kind": "phantom", "ref": "z"},
        })


@pytest.mark.asyncio
async def test_foreach_passes_outer_state_to_inner():
    """Outer state keys remain visible to the inner node — only item_key
    is overlaid per iteration. Lets foreach feed shared context (e.g.
    org_id, repo) to the inner tool without reshuffling state."""
    from kotodama.langgraph_node_resolvers import make_foreach_node
    seen: list[dict] = []

    with patch("kotodama.llm.call_tier_json", side_effect=lambda *a, **kw: {"u": a[2]}):
        node = make_foreach_node({
            "items_path": "items",
            "result_key": "out",
            "node": {
                "kind": "llm", "ref": "t",
                "config": {"input_keys": ["org_id", "item"],
                           "result_key": "_r",
                           "args": {"system": "", "user_template": "{org_id}:{item}"}},
            },
        })
        # Spy via patching the call_tier_json invocation arg capture
        call_log: list[tuple] = []

        def _spy(tier, system, user, **kw):
            call_log.append((tier, user))
            return {"u": user}

        with patch("kotodama.llm.call_tier_json", side_effect=_spy):
            out = await node({"org_id": "ORG1", "items": ["a", "b"]})

    assert out["out"] == [{"_r": {"u": "ORG1:a"}}, {"_r": {"u": "ORG1:b"}}]
    assert call_log == [("t", "ORG1:a"), ("t", "ORG1:b")]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _async_return(value):
    return value
