"""End-to-end smoke test for the MCP self-evolution loop (ADR-2605082000).

Wires the full chain in-process, no HTTP, no aiohttp test server:

    LangGraph node (kind=mcp_tool ref=mcp://...)
      → make_mcp_tool_node._resolve_mcp_nsid (SELECT from vertex_mcp_tool_def)
      → POST {actor_host}/xrpc/com.etzhayyim.mcp.message  (httpx, mocked)
      → mcp_dispatch.handle_envelope
      → MCP_HANDLERS[nsid]  (real, from build_default_handlers())
      → task_echo / task_* result
      → wrapped in {"result": ...}
      → returned to node, written to state[result_key]

Goal: catch resolver/dispatcher contract regressions BEFORE any operator
flips deployment pins (saikin r_20260509180000, ki r_20260509220000).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_pool_for_registry(actor_host: str):
    """Build a fake psycopg pool that returns ``actor_host`` for any nsid."""
    cur = MagicMock()
    cur.fetchone = AsyncMock(return_value=(actor_host,))
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=cur)

    @asynccontextmanager
    async def _cm():
        yield conn

    pool = MagicMock()
    pool.connection = _cm
    return pool


async def _async_return(v):
    return v


def _httpx_to_handle_envelope(handlers):
    """Build a fake httpx.AsyncClient that round-trips POST → handle_envelope."""
    from kotodama.mcp_dispatch import handle_envelope

    class _Resp:
        def __init__(self, status, body):
            self._status = status
            self._body = body

        def raise_for_status(self):
            if self._status >= 400:
                raise RuntimeError(f"http {self._status}: {self._body}")

        def json(self):
            return self._body

    class _Client:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass

        async def post(self, url, json=None, headers=None):
            assert url.endswith("/xrpc/com.etzhayyim.mcp.message"), f"unexpected URL: {url}"
            status, body = await handle_envelope(json, handlers)
            return _Resp(status, body)

    return _Client


@pytest.mark.asyncio
async def test_e2e_const_echo_via_resolver_and_dispatcher():
    """mcp://com.etzhayyim.tools.const.echo with config.args.constant flows end-to-end."""
    from kotodama import langgraph_node_resolvers as resolvers
    from kotodama.mcp_dispatch import build_default_handlers

    resolvers._MCP_REGISTRY_CACHE.clear()
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.const.echo" in handlers, "const.echo must be registered"

    pool = _mock_pool_for_registry("ki.etzhayyim.com")
    cfg = {
        "input_keys": [],
        "result_key": "out",
        "args": {
            "name": "com.etzhayyim.tools.const.echo",
            "constant": {"bloomSkipped": True, "bloomId": None},
        },
    }
    node = resolvers.make_mcp_tool_node(
        "mcp://com.etzhayyim.tools.const.echo",
        cfg,
        pool_factory=lambda: _async_return(pool),
    )

    fake_httpx = _httpx_to_handle_envelope(handlers)
    with patch("httpx.AsyncClient", fake_httpx):
        result = await node({"unrelated": "state"})

    # The whole MCP envelope response is written to state[result_key].
    # handle_envelope wraps in {"result": ...} and task_echo returns the
    # constant verbatim (a dict).
    assert result == {
        "out": {
            "result": {"bloomSkipped": True, "bloomId": None},
        },
    }


@pytest.mark.asyncio
async def test_e2e_actor_tool_input_keys_drive_arguments():
    """`input_keys` pull state values into envelope.params.arguments;
    handler receives them as kwargs and the result threads back through."""
    from kotodama import langgraph_node_resolvers as resolvers

    resolvers._MCP_REGISTRY_CACHE.clear()

    captured = {}

    async def _fake_form_colony(*, signalIds=None, **_):
        captured["signalIds"] = signalIds
        return {"colonyId": "c-7", "memberCount": len(signalIds or [])}

    handlers = {"com.etzhayyim.apps.saikin.formColony": _fake_form_colony}

    pool = _mock_pool_for_registry("saikin.etzhayyim.com")
    cfg = {
        "input_keys": ["signalIds"],
        "result_key": "formOut",
        "args": {"name": "com.etzhayyim.apps.saikin.formColony"},
    }
    node = resolvers.make_mcp_tool_node(
        "mcp://com.etzhayyim.apps.saikin.formColony",
        cfg,
        pool_factory=lambda: _async_return(pool),
    )

    fake_httpx = _httpx_to_handle_envelope(handlers)
    with patch("httpx.AsyncClient", fake_httpx):
        result = await node({"signalIds": ["s1", "s2", "s3"]})

    assert captured["signalIds"] == ["s1", "s2", "s3"]
    assert result == {"formOut": {"result": {"colonyId": "c-7", "memberCount": 3}}}


@pytest.mark.asyncio
async def test_e2e_unknown_nsid_surfaces_dispatcher_404():
    """A node bound to an unregistered NSID propagates the 404 envelope
    (httpx raise_for_status → caller sees the error). Catches the
    'forgot to add the actor to _DEFAULT_ACTORS' regression."""
    from kotodama import langgraph_node_resolvers as resolvers

    resolvers._MCP_REGISTRY_CACHE.clear()

    pool = _mock_pool_for_registry("nonexistent.etzhayyim.com")
    cfg = {
        "input_keys": [],
        "result_key": "out",
        "args": {"name": "com.etzhayyim.apps.ghost.haunt"},
    }
    node = resolvers.make_mcp_tool_node(
        "mcp://com.etzhayyim.apps.ghost.haunt",
        cfg,
        pool_factory=lambda: _async_return(pool),
    )

    handlers: dict = {}  # empty registry — simulating a missing actor wiring
    fake_httpx = _httpx_to_handle_envelope(handlers)
    with patch("httpx.AsyncClient", fake_httpx):
        with pytest.raises(RuntimeError, match="http 404"):
            await node({})


@pytest.mark.asyncio
async def test_e2e_full_data_chain_fetch_extract_transform_insert():
    """ADR-2605082000 §2 — demonstrate the full data-only chain that
    replaces per-actor py_primitive Python code:

        node A: http.fetch     → state.fetchOut (with body)
        node B: json.extract   → state.itemsOut (Crossref message.items)
        node C: transform.map  → state.rowsOut (vertex_work rows)
        node D: sql.exec       → state.insertOut (rowCount)

    Each node is bound via mcp:// + input_paths. State threads through.
    Mocks httpx + db_alchemy + the registry pool — no real DB / network."""
    import sys, types
    from kotodama import langgraph_node_resolvers as resolvers
    from kotodama.tools_json_worker_main import task_json_extract
    from kotodama.tools_transform_worker_main import task_transform_map
    from kotodama.tools_http_worker_main import task_http_fetch
    from kotodama.tools_sql_worker_main import task_sql_exec

    resolvers._MCP_REGISTRY_CACHE.clear()

    # --- mock httpx — supports BOTH .post (MCP envelope) AND .request (upstream HTTP) ---
    crossref_response = {
        "message": {"items": [
            {"DOI": "10.1/abc", "title": ["Hello"]},
            {"DOI": "10.2/def", "title": ["World"]},
        ]},
    }
    class _UpstreamResp:
        def __init__(self, status, body, headers, encoding="utf-8"):
            self.status_code = status
            self.content = body
            self.headers = headers
            self.encoding = encoding
    class _EnvelopeResp:
        def __init__(self, status, body):
            self._status = status
            self._body = body
        def raise_for_status(self):
            if self._status >= 400:
                raise RuntimeError(f"http {self._status}: {self._body}")
        def json(self):
            return self._body

    # --- mock db_alchemy for sql.exec ---
    captured = {}
    def _fake_executemany(clause, rows, chunk_size=500):
        captured["rows"] = list(rows)
        return len(rows)
    fake_sa = types.ModuleType("sqlalchemy")
    fake_sa.text = lambda s: s
    fake_db = types.ModuleType("kotodama.db_alchemy")
    fake_db.sa_executemany = _fake_executemany
    fake_db.sa_rowcount = lambda *a, **k: 0

    # --- handlers registry (real handlers, mocks only at the I/O boundary) ---
    handlers = {
        "com.etzhayyim.tools.http.fetch":     task_http_fetch,
        "com.etzhayyim.tools.json.extract":   task_json_extract,
        "com.etzhayyim.tools.transform.map":  task_transform_map,
        "com.etzhayyim.tools.sql.exec":       task_sql_exec,
    }
    pool = _mock_pool_for_registry("copyright.etzhayyim.com")
    pool_factory = lambda: _async_return(pool)

    # Unified httpx mock: .post is the MCP envelope path (resolver →
    # dispatcher round-trip), .request is the upstream HTTP fetch
    # (task_http_fetch → Crossref). URL discriminates which is being called.
    from kotodama.mcp_dispatch import handle_envelope
    class _UnifiedClient:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def post(self, url, json=None, headers=None):
            assert url.endswith("/xrpc/com.etzhayyim.mcp.message"), f"unexpected url {url}"
            status, body = await handle_envelope(json, handlers)
            return _EnvelopeResp(status, body)
        async def request(self, m, url, **kwargs):
            import json as _j
            return _UpstreamResp(
                200,
                _j.dumps(crossref_response).encode("utf-8"),
                {"content-type": "application/json"},
            )

    # --- build 4 chain nodes ---
    fetch_node = resolvers.make_mcp_tool_node(
        "mcp://com.etzhayyim.tools.http.fetch",
        {
            "input_keys": [],
            "result_key": "fetchOut",
            "args": {
                "name": "com.etzhayyim.tools.http.fetch",
                "url":  "https://api.crossref.org/works",
            },
        },
        pool_factory=pool_factory,
    )
    # NOTE: the dispatcher wraps every handler's return in `{"result": ...}`,
    # so downstream input_paths must navigate through `.result.` to reach
    # the inner payload. (Iter14's test_e2e_const_echo also shows this.)
    extract_node = resolvers.make_mcp_tool_node(
        "mcp://com.etzhayyim.tools.json.extract",
        {
            "input_keys": [],
            "input_paths": {"json": "fetchOut.result.body"},
            "result_key": "itemsOut",
            "args": {
                "name": "com.etzhayyim.tools.json.extract",
                "path": "message.items",
            },
        },
        pool_factory=pool_factory,
    )
    transform_node = resolvers.make_mcp_tool_node(
        "mcp://com.etzhayyim.tools.transform.map",
        {
            "input_keys": [],
            "input_paths": {"input": "itemsOut.result.value"},
            "result_key": "rowsOut",
            "args": {
                "name": "com.etzhayyim.tools.transform.map",
                "mapping": {
                    "doi": "$.DOI",
                    "title": "$.title[0]",
                    "vertex_id": {"fmt": "at://copyright/{DOI}"},
                    "registry": {"const": "crossref"},
                },
                "defaults": {"berne_automatic": True},
            },
        },
        pool_factory=pool_factory,
    )
    insert_node = resolvers.make_mcp_tool_node(
        "mcp://com.etzhayyim.tools.sql.exec",
        {
            "input_keys": [],
            "input_paths": {"rows": "rowsOut.result.rows"},
            "result_key": "insertOut",
            "args": {
                "name": "com.etzhayyim.tools.sql.exec",
                "sql": "INSERT INTO vertex_work (doi, title, vertex_id, registry, berne_automatic) VALUES (%(doi)s, %(title)s, %(vertex_id)s, %(registry)s, %(berne_automatic)s)",
                "confirmWrite": True,
            },
        },
        pool_factory=pool_factory,
    )

    # --- run chain in sequence, single httpx + sqlalchemy mock context ---
    state: dict = {}
    with patch("httpx.AsyncClient", _UnifiedClient), \
         patch.dict(sys.modules, {"sqlalchemy": fake_sa, "kotodama.db_alchemy": fake_db}):
        # 1. fetch (resolver POSTs envelope → handle_envelope → task_http_fetch → upstream Crossref via _UnifiedClient.request)
        state.update(await fetch_node(state))
        # 2. extract (resolver → handle_envelope → task_json_extract)
        state.update(await extract_node(state))
        # 3. transform (resolver → handle_envelope → task_transform_map)
        state.update(await transform_node(state))
        # 4. insert (resolver → handle_envelope → task_sql_exec → fake sa_executemany)
        state.update(await insert_node(state))

    # --- verify the chain threaded data correctly ---
    assert state["insertOut"]["result"]["rowCount"] == 2
    assert captured["rows"][0] == {
        "doi": "10.1/abc",
        "title": "Hello",
        "vertex_id": "at://copyright/10.1/abc",
        "registry": "crossref",
        "berne_automatic": True,
    }
    assert captured["rows"][1]["doi"] == "10.2/def"


@pytest.mark.asyncio
async def test_e2e_input_paths_chain_through_dispatcher():
    """ADR-2605082000 §2 — node-chain pattern.
    A node binding `input_paths` walks nested state (= upstream node's output)
    and threads the sub-tree to its tool's arguments. End-to-end:
    state has fetchOut.body.message.items, this node extracts items[0].DOI."""
    from kotodama import langgraph_node_resolvers as resolvers
    from kotodama.tools_json_worker_main import task_json_extract

    resolvers._MCP_REGISTRY_CACHE.clear()
    handlers = {"com.etzhayyim.tools.json.extract": task_json_extract}

    pool = _mock_pool_for_registry("copyright.etzhayyim.com")
    cfg = {
        "input_keys": [],
        "input_paths": {"json": "fetchOut.body"},
        "result_key": "out",
        "args": {"name": "com.etzhayyim.tools.json.extract", "path": "message.items[0].DOI"},
    }
    node = resolvers.make_mcp_tool_node(
        "mcp://com.etzhayyim.tools.json.extract",
        cfg,
        pool_factory=lambda: _async_return(pool),
    )

    fake_httpx = _httpx_to_handle_envelope(handlers)
    state = {
        "fetchOut": {
            "body": {"message": {"items": [{"DOI": "10.1/abc"}, {"DOI": "10.2/def"}]}},
        },
    }
    with patch("httpx.AsyncClient", fake_httpx):
        result = await node(state)

    assert result == {"out": {"result": {"value": "10.1/abc"}}}


@pytest.mark.asyncio
async def test_e2e_registry_resolution_is_cached():
    """A second invocation must reuse the resolved actor_host and not hit
    the registry pool again. This protects RisingWave from hot-loop SELECTs."""
    from kotodama import langgraph_node_resolvers as resolvers

    resolvers._MCP_REGISTRY_CACHE.clear()
    pool = _mock_pool_for_registry("ki.etzhayyim.com")

    async def _echo(*, constant=None, **_):
        return constant or {}

    handlers = {"com.etzhayyim.tools.const.echo": _echo}

    cfg = {
        "input_keys": [],
        "result_key": "out",
        "args": {
            "name": "com.etzhayyim.tools.const.echo",
            "constant": {"x": 1},
        },
    }
    node = resolvers.make_mcp_tool_node(
        "mcp://com.etzhayyim.tools.const.echo",
        cfg,
        pool_factory=lambda: _async_return(pool),
    )

    fake_httpx = _httpx_to_handle_envelope(handlers)
    with patch("httpx.AsyncClient", fake_httpx):
        await node({})
        await node({})
        await node({})

    # Three node calls, but only one SELECT against vertex_mcp_tool_def.
    pool_conn = pool.connection().__aenter__  # not strictly callable here
    # Validate by counting execute calls on the original cursor mock:
    # the helper builds one connection mock per pool; reach in.
    select_calls = 0
    # The mock connection is captured by the closure; introspect via pool:
    async with pool.connection() as conn:
        select_calls = conn.execute.await_count
    assert select_calls == 1, f"expected 1 SELECT, got {select_calls}"
