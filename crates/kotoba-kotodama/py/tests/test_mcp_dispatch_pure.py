"""Pure unit tests for kotodama.mcp_dispatch.handle_envelope (no aiohttp)."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# handle_envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tools_call_routes_to_registered_handler():
    from kotodama.mcp_dispatch import handle_envelope

    captured: dict = {}

    async def _fake(**kwargs):
        captured.update(kwargs)
        return {"signalCount": 3, "signals": [{"id": "s1"}]}

    handlers = {"com.etzhayyim.apps.saikin.probeEnvironment": _fake}
    status, body = await handle_envelope(
        {
            "method": "tools/call",
            "params": {
                "name": "com.etzhayyim.apps.saikin.probeEnvironment",
                "arguments": {},
            },
        },
        handlers,
    )

    assert status == 200
    assert body == {"result": {"signalCount": 3, "signals": [{"id": "s1"}]}}
    assert captured == {}


@pytest.mark.asyncio
async def test_tools_call_passes_arguments_as_kwargs():
    from kotodama.mcp_dispatch import handle_envelope

    async def _form_colony(**kwargs):
        assert kwargs == {"signalIds": ["s1", "s2", "s3"]}
        return {"colonyId": "c-42", "memberCount": 3}

    handlers = {"com.etzhayyim.apps.saikin.formColony": _form_colony}
    status, body = await handle_envelope(
        {
            "method": "tools/call",
            "params": {
                "name": "com.etzhayyim.apps.saikin.formColony",
                "arguments": {"signalIds": ["s1", "s2", "s3"]},
            },
        },
        handlers,
    )

    assert status == 200
    assert body["result"]["colonyId"] == "c-42"


@pytest.mark.asyncio
async def test_unknown_nsid_returns_404():
    from kotodama.mcp_dispatch import handle_envelope

    status, body = await handle_envelope(
        {"method": "tools/call", "params": {"name": "com.etzhayyim.apps.unknown.thing"}},
        handlers={},
    )

    assert status == 404
    assert "no MCP handler" in body["error"]


@pytest.mark.asyncio
async def test_non_tools_call_method_rejected():
    from kotodama.mcp_dispatch import handle_envelope

    status, body = await handle_envelope(
        {"method": "tools/list"}, handlers={},
    )

    assert status == 400
    assert "unsupported method" in body["error"]


@pytest.mark.asyncio
async def test_missing_name_rejected():
    from kotodama.mcp_dispatch import handle_envelope

    status, body = await handle_envelope(
        {"method": "tools/call", "params": {"arguments": {}}},
        handlers={},
    )

    assert status == 400
    assert "params.name" in body["error"]


@pytest.mark.asyncio
async def test_unexpected_kwargs_become_400():
    """A handler that does not accept extra kwargs surfaces TypeError as 400."""
    from kotodama.mcp_dispatch import handle_envelope

    async def _strict():  # accepts no kwargs at all
        return {"ok": True}

    handlers = {"com.etzhayyim.apps.saikin.lyse": _strict}
    status, body = await handle_envelope(
        {
            "method": "tools/call",
            "params": {
                "name": "com.etzhayyim.apps.saikin.lyse",
                "arguments": {"signalId": "s1"},
            },
        },
        handlers,
    )

    assert status == 400
    assert "com.etzhayyim.apps.saikin.lyse" in body["error"]


# ---------------------------------------------------------------------------
# register_actor_by_convention  (ADR-2605082000 §2.6 dispatcher convention)
# ---------------------------------------------------------------------------


def test_camel_to_snake():
    from kotodama.mcp_dispatch import _camel_to_snake
    assert _camel_to_snake("probeEnvironment") == "probe_environment"
    assert _camel_to_snake("handoffToKi") == "handoff_to_ki"
    assert _camel_to_snake("lyse") == "lyse"
    assert _camel_to_snake("XYZAcronym") == "x_y_z_acronym"


def test_register_actor_by_convention_resolves_task_functions(monkeypatch):
    """`com.etzhayyim.apps.{actor}.{method}` → `kotodama.{actor}_worker_main:task_{snake}`."""
    import sys
    import types
    from kotodama.mcp_dispatch import register_actor_by_convention

    fake_mod = types.ModuleType("kotodama.fakeactor_worker_main")
    async def task_do_something(**_): return {"ok": True}
    async def task_run(**_): return {"ok": True}
    fake_mod.task_do_something = task_do_something
    fake_mod.task_run = task_run
    monkeypatch.setitem(sys.modules, "kotodama.fakeactor_worker_main", fake_mod)

    handlers = register_actor_by_convention(
        "fakeactor", ["doSomething", "run"],
    )

    assert set(handlers.keys()) == {
        "com.etzhayyim.apps.fakeactor.doSomething",
        "com.etzhayyim.apps.fakeactor.run",
    }
    assert handlers["com.etzhayyim.apps.fakeactor.doSomething"] is task_do_something
    assert handlers["com.etzhayyim.apps.fakeactor.run"] is task_run


def test_register_actor_by_convention_module_missing_returns_empty(caplog):
    """Missing actor module degrades gracefully (logged, not raised)."""
    from kotodama.mcp_dispatch import register_actor_by_convention

    with caplog.at_level("WARNING", logger="mcp_dispatch"):
        handlers = register_actor_by_convention(
            "nonexistent_actor_xyz", ["foo", "bar"],
        )
    assert handlers == {}
    assert any("nonexistent_actor_xyz" in r.message for r in caplog.records)


def test_register_actor_by_convention_override_module_and_fn_template(monkeypatch):
    """Per-actor module + fn_template override (used by bulk-51 entries
    where task lives in kotodama.primitives.<actor> with a non-standard name)."""
    import sys
    import types
    from kotodama.mcp_dispatch import register_actor_by_convention

    fake_mod = types.ModuleType("kotodama.primitives.adsk")
    async def task_adsk_dataset_ingest_all(**_): return {"ok": True}
    fake_mod.task_adsk_dataset_ingest_all = task_adsk_dataset_ingest_all
    monkeypatch.setitem(sys.modules, "kotodama.primitives.adsk", fake_mod)

    handlers = register_actor_by_convention(
        "adsk", ["datasetIngestAll"],
        module_template="kotodama.primitives.adsk",
        fn_template="task_adsk_{snake}",
    )

    assert list(handlers.keys()) == ["com.etzhayyim.apps.adsk.datasetIngestAll"]
    assert handlers["com.etzhayyim.apps.adsk.datasetIngestAll"] is task_adsk_dataset_ingest_all


def test_register_actor_by_convention_missing_method_skipped(monkeypatch, caplog):
    """If a single method lacks task_*, it's skipped while siblings register."""
    import sys
    import types
    from kotodama.mcp_dispatch import register_actor_by_convention

    fake_mod = types.ModuleType("kotodama.partial_worker_main")
    async def task_present(**_): return {"ok": True}
    fake_mod.task_present = task_present
    # Note: no task_missing.
    monkeypatch.setitem(sys.modules, "kotodama.partial_worker_main", fake_mod)

    with caplog.at_level("WARNING", logger="mcp_dispatch"):
        handlers = register_actor_by_convention("partial", ["present", "missing"])

    assert list(handlers.keys()) == ["com.etzhayyim.apps.partial.present"]
    assert any("com.etzhayyim.apps.partial.missing" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# tools_const_worker_main.task_echo  (ADR-2605082000 §2.6 follow-up)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_echo_returns_constant_verbatim():
    from kotodama.tools_const_worker_main import task_echo
    out = await task_echo(constant={"bloomSkipped": True, "bloomId": None})
    assert out == {"bloomSkipped": True, "bloomId": None}


@pytest.mark.asyncio
async def test_task_echo_missing_constant_returns_error():
    from kotodama.tools_const_worker_main import task_echo
    out = await task_echo()
    assert "error" in out


@pytest.mark.asyncio
async def test_task_echo_non_object_constant_returns_error():
    from kotodama.tools_const_worker_main import task_echo
    out = await task_echo(constant="not-an-object")
    assert "error" in out


@pytest.mark.asyncio
async def test_task_echo_ignores_extra_kwargs():
    from kotodama.tools_const_worker_main import task_echo
    out = await task_echo(constant={"x": 1}, ignored="yes")
    assert out == {"x": 1}


# ---------------------------------------------------------------------------
# tools.time.now / tools.crypto.hash  (ADR-2605082000 Phase D)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_time_now_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.time.now" in handlers


@pytest.mark.asyncio
async def test_time_now_iso_default_utc():
    from kotodama.tools_time_worker_main import task_time_now
    out = await task_time_now()
    assert "now" in out and isinstance(out["now"], str)
    # ISO 8601 with timezone offset (UTC = +00:00)
    assert out["now"].endswith("+00:00")


@pytest.mark.asyncio
async def test_time_now_epoch_seconds_and_ms():
    from kotodama.tools_time_worker_main import task_time_now
    s = await task_time_now(format="epoch_s")
    ms = await task_time_now(format="epoch_ms")
    assert isinstance(s["now"], float) and s["now"] > 1_700_000_000
    assert isinstance(ms["now"], int) and ms["now"] > 1_700_000_000_000
    # ms should be roughly 1000× s
    assert abs(ms["now"] / 1000 - s["now"]) < 5  # 5s slack


@pytest.mark.asyncio
async def test_time_now_unknown_tz_falls_back_with_error():
    from kotodama.tools_time_worker_main import task_time_now
    out = await task_time_now(format="iso", tz="Bogus/Place")
    assert "now" in out
    assert "error" in out and "unknown tz" in out["error"]


@pytest.mark.asyncio
async def test_time_now_invalid_format_returns_error():
    from kotodama.tools_time_worker_main import task_time_now
    out = await task_time_now(format="rfc822")
    assert "error" in out and "format" in out["error"]


@pytest.mark.asyncio
async def test_crypto_hash_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.crypto.hash" in handlers


@pytest.mark.asyncio
async def test_crypto_hash_sha256_hex_known_vector():
    from kotodama.tools_crypto_worker_main import task_crypto_hash
    # Known: sha256("abc") = ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
    out = await task_crypto_hash(algorithm="sha256", input="abc", encoding="hex")
    assert out == {"hash": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"}


@pytest.mark.asyncio
async def test_crypto_hash_md5_base64_known_vector():
    from kotodama.tools_crypto_worker_main import task_crypto_hash
    # md5("") = d41d8cd98f00b204e9800998ecf8427e → base64 1B2M2Y8AsgTpgAmY7PhCfg==
    out = await task_crypto_hash(algorithm="md5", input="", encoding="base64")
    assert out == {"hash": "1B2M2Y8AsgTpgAmY7PhCfg=="}


@pytest.mark.asyncio
async def test_crypto_hash_bytes_input():
    from kotodama.tools_crypto_worker_main import task_crypto_hash
    out = await task_crypto_hash(algorithm="sha256", input=b"abc", encoding="hex")
    assert out["hash"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


@pytest.mark.asyncio
async def test_crypto_hash_invalid_algorithm():
    from kotodama.tools_crypto_worker_main import task_crypto_hash
    out = await task_crypto_hash(algorithm="rot13", input="x")
    assert "error" in out and "algorithm" in out["error"]


@pytest.mark.asyncio
async def test_crypto_hash_missing_input():
    from kotodama.tools_crypto_worker_main import task_crypto_hash
    out = await task_crypto_hash(algorithm="sha256")
    assert "error" in out and "input" in out["error"]


@pytest.mark.asyncio
async def test_transform_map_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.transform.map" in handlers


@pytest.mark.asyncio
async def test_task_transform_map_path_const_fmt():
    """Apply mapping with all 3 spec forms (path / const / fmt)."""
    from kotodama.tools_transform_worker_main import task_transform_map
    items = [
        {"DOI": "10.1/abc", "title": ["Hello"]},
        {"DOI": "10.2/def", "title": ["World"]},
    ]
    out = await task_transform_map(
        input=items,
        mapping={
            "doi":   "$.DOI",
            "title": "$.title[0]",
            "vertex_id": {"fmt": "at://copyright/{DOI}"},
            "registry": {"const": "crossref"},
        },
        defaults={"berne_automatic": True},
    )
    assert out["rowCount"] == 2
    assert out["skipped"] == 0
    assert out["rows"][0] == {
        "berne_automatic": True,
        "doi": "10.1/abc",
        "title": "Hello",
        "vertex_id": "at://copyright/10.1/abc",
        "registry": "crossref",
    }
    assert out["rows"][1]["doi"] == "10.2/def"


@pytest.mark.asyncio
async def test_task_transform_map_default_path_fallback():
    from kotodama.tools_transform_worker_main import task_transform_map
    out = await task_transform_map(
        input=[{"a": 1}],
        mapping={
            "ok":  {"path": "$.a", "default": -1},
            "fb":  {"path": "$.b", "default": "fallback"},
        },
    )
    assert out["rows"][0] == {"ok": 1, "fb": "fallback"}


@pytest.mark.asyncio
async def test_task_transform_map_skips_non_dict_rows():
    from kotodama.tools_transform_worker_main import task_transform_map
    out = await task_transform_map(
        input=[{"a": 1}, "not-a-dict", 42, {"a": 2}],
        mapping={"a": "$.a"},
    )
    assert out["rowCount"] == 2
    assert out["skipped"] == 2


@pytest.mark.asyncio
async def test_task_transform_map_required_fields():
    from kotodama.tools_transform_worker_main import task_transform_map
    out = await task_transform_map(input=[])
    assert "error" in out
    out2 = await task_transform_map(mapping={})
    assert "error" in out2
    out3 = await task_transform_map(input="not-array", mapping={})
    assert "error" in out3


@pytest.mark.asyncio
async def test_json_extract_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.json.extract" in handlers


@pytest.mark.asyncio
async def test_task_json_extract_dotted_path():
    from kotodama.tools_json_worker_main import task_json_extract
    payload = {"message": {"items": [{"DOI": "10.1/abc"}, {"DOI": "10.2/def"}]}}
    out = await task_json_extract(json=payload, path="message.items")
    assert out["value"] == [{"DOI": "10.1/abc"}, {"DOI": "10.2/def"}]
    out2 = await task_json_extract(json=payload, path="message.items[0].DOI")
    assert out2["value"] == "10.1/abc"
    out3 = await task_json_extract(json=payload, path="missing.path", default="fallback")
    assert out3["value"] == "fallback"
    import json as _j
    out4 = await task_json_extract(json=_j.dumps(payload), path="message.items[1].DOI")
    assert out4["value"] == "10.2/def"


@pytest.mark.asyncio
async def test_task_json_extract_star_flatten():
    from kotodama.tools_json_worker_main import task_json_extract
    out = await task_json_extract(
        json={"data": {"a": {"v": 1}, "b": {"v": 2}}},
        path="data.*",
    )
    assert out["value"] == [{"v": 1}, {"v": 2}]


@pytest.mark.asyncio
async def test_task_json_extract_errors():
    from kotodama.tools_json_worker_main import task_json_extract
    out = await task_json_extract(path="x")
    assert "error" in out
    out2 = await task_json_extract(json="not-json", path="x")
    assert "error" in out2


@pytest.mark.asyncio
async def test_sql_exec_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.sql.exec" in handlers


@pytest.mark.asyncio
async def test_task_sql_exec_strict_guards():
    """Defense-in-depth: confirmWrite + INSERT/UPDATE/UPSERT/WITH only."""
    from kotodama.tools_sql_worker_main import task_sql_exec

    out1 = await task_sql_exec(sql="INSERT INTO x VALUES (1)")
    assert "error" in out1 and "confirmWrite" in out1["error"]

    out2 = await task_sql_exec(sql="SELECT 1", confirmWrite=True)
    assert "error" in out2

    out3 = await task_sql_exec(sql="DROP TABLE x", confirmWrite=True)
    assert "error" in out3

    out4 = await task_sql_exec(sql="DELETE FROM x", confirmWrite=True)
    assert "error" in out4

    out5 = await task_sql_exec(sql="ALTER TABLE x ADD COLUMN y INT", confirmWrite=True)
    assert "error" in out5


@pytest.mark.asyncio
async def test_task_sql_exec_executemany_path(monkeypatch):
    """When `rows` is supplied, sa_executemany is used in batch mode."""
    import sys, types
    from kotodama.tools_sql_worker_main import task_sql_exec

    captured = {}
    def _fake_executemany(clause, rows, chunk_size=500):
        captured["clause"] = str(clause)
        captured["rows"] = list(rows)
        return len(rows)

    fake_sa = types.ModuleType("sqlalchemy")
    fake_sa.text = lambda s: s
    monkeypatch.setitem(sys.modules, "sqlalchemy", fake_sa)

    fake_db = types.ModuleType("kotodama.db_alchemy")
    fake_db.sa_executemany = _fake_executemany
    fake_db.sa_rowcount = lambda *a, **k: 0
    monkeypatch.setitem(sys.modules, "kotodama.db_alchemy", fake_db)

    out = await task_sql_exec(
        sql="INSERT INTO vertex_x (id, name) VALUES (%(id)s, %(name)s)",
        rows=[{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
        confirmWrite=True,
    )
    assert out["rowCount"] == 2
    assert captured["rows"] == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]


@pytest.mark.asyncio
async def test_sql_insert_row_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.sql.insert_row" in handlers


@pytest.mark.asyncio
async def test_sql_insert_row_rejects_invalid_table_names():
    from kotodama.tools_sql_worker_main import task_sql_insert_row
    bad_inputs = ["", "x; DROP TABLE y", "v.public.x", "DROP TABLE x"]
    for bad in bad_inputs:
        out = await task_sql_insert_row(table=bad, row={"a": 1})
        assert "error" in out and "invalid table name" in out["error"], bad


@pytest.mark.asyncio
async def test_sql_insert_row_rejects_invalid_column_names():
    from kotodama.tools_sql_worker_main import task_sql_insert_row
    out = await task_sql_insert_row(
        table="vertex_x", row={"valid": 1, "bad-col": 2, "x;y": 3},
    )
    assert "error" in out and "invalid column names" in out["error"]


@pytest.mark.asyncio
async def test_sql_insert_row_rejects_empty_row():
    from kotodama.tools_sql_worker_main import task_sql_insert_row
    out1 = await task_sql_insert_row(table="vertex_x", row=None)
    assert "error" in out1 and "row" in out1["error"]
    out2 = await task_sql_insert_row(table="vertex_x", row={})
    assert "error" in out2 and "row" in out2["error"]


@pytest.mark.asyncio
async def test_sql_insert_row_basic_insert(monkeypatch):
    """Happy path: builds Table dynamically, calls sa_rowcount with bindings,
    returns the (passed-through) vertex_id."""
    import sys, types
    from kotodama.tools_sql_worker_main import task_sql_insert_row

    captured = {}
    def _fake_rowcount(stmt, bindings):
        captured["stmt"] = stmt
        captured["bindings"] = dict(bindings)
        return 1

    fake_sa = types.ModuleType("sqlalchemy")
    class _FakeColumn:
        def __init__(self, name, type_):
            self.name = name
    class _FakeTable:
        def __init__(self, name, metadata, *cols, extend_existing=False):
            self.name = name
            self.cols = [c.name for c in cols]
        def insert(self):
            return f"INSERT INTO {self.name} ({','.join(self.cols)})"
    fake_sa.Table = _FakeTable
    fake_sa.Column = _FakeColumn
    fake_sa.String = str
    fake_sa.MetaData = type("MD", (), {})
    monkeypatch.setitem(sys.modules, "sqlalchemy", fake_sa)

    fake_db = types.ModuleType("kotodama.db_alchemy")
    fake_db.sa_metadata = lambda: object()
    fake_db.sa_rowcount = _fake_rowcount
    monkeypatch.setitem(sys.modules, "kotodama.db_alchemy", fake_db)

    out = await task_sql_insert_row(
        table="vertex_hr_event",
        row={"vertex_id": "at://x/y/z", "name": "alice", "salary": 100000},
    )
    assert out == {"vertexId": "at://x/y/z", "ok": True}
    assert captured["bindings"]["name"] == "alice"
    assert captured["bindings"]["salary"] == "100000"   # coerced to str
    assert "INSERT INTO vertex_hr_event" in captured["stmt"]


@pytest.mark.asyncio
async def test_sql_insert_row_derives_vertex_id_from_template(monkeypatch):
    """When row.vertex_id is absent and vertex_id_template is given, the
    primitive renders the template using owner_did + collection + stamp +
    nanoid8 placeholders, and returns the derived id."""
    import sys, types, re as _re
    from kotodama.tools_sql_worker_main import task_sql_insert_row

    captured_bindings = {}
    def _fake_rowcount(_stmt, bindings):
        captured_bindings.update(dict(bindings))
        return 1

    fake_sa = types.ModuleType("sqlalchemy")
    fake_sa.Table = lambda *a, **kw: type("T", (), {"insert": lambda self: "ins"})()
    fake_sa.Column = lambda *a, **kw: object()
    fake_sa.String = str
    fake_sa.MetaData = type("MD", (), {})
    monkeypatch.setitem(sys.modules, "sqlalchemy", fake_sa)

    fake_db = types.ModuleType("kotodama.db_alchemy")
    fake_db.sa_metadata = lambda: object()
    fake_db.sa_rowcount = _fake_rowcount
    monkeypatch.setitem(sys.modules, "kotodama.db_alchemy", fake_db)

    out = await task_sql_insert_row(
        table="vertex_hr_event",
        row={"name": "alice"},
        vertex_id_template="at://{owner_did}/{collection}/{stamp}-{nanoid8}",
        owner_did="did:web:bpmn.etzhayyim.com",
        collection="com.etzhayyim.apps.hr.event",
    )
    assert out["ok"] is True
    vid = out["vertexId"]
    # Shape: at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.hr.event/<14digits>-<8hex>
    assert _re.match(
        r"^at://did:web:bpmn\.etzhayyim\.ai/ai\.etzhayyim\.apps\.hr\.event/\d{14}-[0-9a-f]{8}$",
        vid,
    ), f"unexpected vid shape: {vid!r}"
    assert captured_bindings["vertex_id"] == vid


@pytest.mark.asyncio
async def test_sql_insert_row_existing_vertex_id_not_overwritten(monkeypatch):
    """If row already has vertex_id, the template is ignored — caller has
    final say. (Mirrors etzhayyim_company_ops `_db_insert` semantics.)"""
    import sys, types
    from kotodama.tools_sql_worker_main import task_sql_insert_row

    fake_sa = types.ModuleType("sqlalchemy")
    fake_sa.Table = lambda *a, **kw: type("T", (), {"insert": lambda self: "ins"})()
    fake_sa.Column = lambda *a, **kw: object()
    fake_sa.String = str
    fake_sa.MetaData = type("MD", (), {})
    monkeypatch.setitem(sys.modules, "sqlalchemy", fake_sa)

    fake_db = types.ModuleType("kotodama.db_alchemy")
    fake_db.sa_metadata = lambda: object()
    fake_db.sa_rowcount = lambda *a, **k: 1
    monkeypatch.setitem(sys.modules, "kotodama.db_alchemy", fake_db)

    out = await task_sql_insert_row(
        table="vertex_x",
        row={"vertex_id": "at://caller-chose-this", "name": "alice"},
        vertex_id_template="at://OVERRIDDEN",
        owner_did="x", collection="y",
    )
    assert out["vertexId"] == "at://caller-chose-this"


@pytest.mark.asyncio
async def test_http_fetch_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.http.fetch" in handlers


@pytest.mark.asyncio
async def test_task_http_fetch_requires_url_and_blocks_writes():
    from kotodama.tools_http_worker_main import task_http_fetch
    out = await task_http_fetch()
    assert "error" in out and "url" in out["error"]
    out2 = await task_http_fetch(url="https://x.example", method="POST")
    assert "error" in out2 and "allowWrite" in out2["error"]
    out3 = await task_http_fetch(url="https://x.example", method="UNKNOWN")
    assert "error" in out3 and "unsupported" in out3["error"]


@pytest.mark.asyncio
async def test_task_http_fetch_returns_envelope(monkeypatch):
    """Mock httpx.AsyncClient and verify the envelope shape (status / body /
    isText for text/json content)."""
    import sys, types
    from kotodama.tools_http_worker_main import task_http_fetch

    class _Resp:
        def __init__(self, status, body, headers, encoding="utf-8"):
            self.status_code = status
            self.content = body
            self.headers = headers
            self.encoding = encoding

    class _Client:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def request(self, m, url, **kwargs):
            return _Resp(
                200, b'{"hello":"world"}',
                {"content-type": "application/json"},
            )

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.AsyncClient = _Client
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    out = await task_http_fetch(url="https://x.example/data")
    assert out["status"] == 200
    assert out["isText"] is True
    assert out["body"] == '{"hello":"world"}'


@pytest.mark.asyncio
async def test_sql_query_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.sql.query" in handlers


@pytest.mark.asyncio
async def test_task_sql_query_rejects_non_select():
    """Strict guard: only SELECT / WITH … SELECT accepted."""
    from kotodama.tools_sql_worker_main import task_sql_query
    bad = await task_sql_query(sql="DELETE FROM vertex_repo_commit")
    assert "error" in bad and "SELECT or WITH" in bad["error"]
    bad2 = await task_sql_query(sql="INSERT INTO x VALUES (1)")
    assert "error" in bad2
    bad3 = await task_sql_query(sql="DROP TABLE vertex_actor")
    assert "error" in bad3
    bad4 = await task_sql_query(sql="")
    assert "error" in bad4


@pytest.mark.asyncio
async def test_task_sql_query_accepts_select_and_with(monkeypatch):
    """SELECT / WITH (with leading whitespace + comment) pass the guard
    and call sa_query. Mocks db_alchemy."""
    import sys, types
    from kotodama.tools_sql_worker_main import task_sql_query

    captured = {}

    def _fake_sa_query(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        # Return SQLAlchemy-style _mapping rows via simple dicts.
        return [{"id": 1, "name": "row1"}, {"id": 2, "name": "row2"}]

    fake_mod = types.ModuleType("kotodama.db_alchemy")
    fake_mod.sa_query = _fake_sa_query
    monkeypatch.setitem(sys.modules, "kotodama.db_alchemy", fake_mod)

    out = await task_sql_query(sql="SELECT id, name FROM x WHERE id = %(i)s", params={"i": 1})
    assert out["rowCount"] == 2
    assert out["rows"][0]["id"] == 1
    assert captured["params"] == {"i": 1}

    out2 = await task_sql_query(sql="  /* comment */ WITH t AS (SELECT 1) SELECT * FROM t")
    assert "error" not in out2

    # Limit caps the response.
    out3 = await task_sql_query(sql="SELECT 1", limit=1)
    assert out3["rowCount"] == 1
    assert len(out3["rows"]) == 1


@pytest.mark.asyncio
async def test_task_sql_query_threads_extra_kwargs_into_params(monkeypatch):
    """input_keys-derived state values flow into named SQL binds.
    Explicit `params` wins on key collision."""
    import sys, types
    from kotodama.tools_sql_worker_main import task_sql_query

    captured = {}
    def _fake_sa_query(sql, params=None):
        captured["params"] = params
        return []
    fake_mod = types.ModuleType("kotodama.db_alchemy")
    fake_mod.sa_query = _fake_sa_query
    monkeypatch.setitem(sys.modules, "kotodama.db_alchemy", fake_mod)

    # extra kwargs become params
    await task_sql_query(
        sql="SELECT 1 WHERE x = %(foo)s",
        foo="bar",
        industry_codes=["a", "b"],
    )
    assert captured["params"] == {"foo": "bar", "industry_codes": ["a", "b"]}

    # explicit params wins on conflict
    await task_sql_query(
        sql="SELECT 1",
        params={"foo": "explicit"},
        foo="kwarg",
    )
    assert captured["params"]["foo"] == "explicit"


@pytest.mark.asyncio
async def test_llm_chat_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.llm.chat" in handlers


@pytest.mark.asyncio
async def test_task_llm_chat_requires_user_prompt():
    from kotodama.tools_llm_worker_main import task_llm_chat
    out = await task_llm_chat()
    assert "error" in out


@pytest.mark.asyncio
async def test_task_llm_chat_forwards_kwargs(monkeypatch):
    """Kwargs threading from MCP envelope → task_generic_llm_chat."""
    import sys, types
    captured = {}

    async def _fake_chat(*, tier, system, user, maxTokens, temperature):
        captured.update({
            "tier": tier, "system": system, "user": user,
            "maxTokens": maxTokens, "temperature": temperature,
        })
        return {"content": "ok", "tier": tier}

    fake_mod = types.ModuleType("kotodama.zeebe_worker_main")
    fake_mod.task_generic_llm_chat = _fake_chat
    monkeypatch.setitem(sys.modules, "kotodama.zeebe_worker_main", fake_mod)

    from kotodama.tools_llm_worker_main import task_llm_chat
    out = await task_llm_chat(
        tier="deep", system="be concise", user="hello",
        maxTokens=42, temperature=0.7,
    )
    assert out == {"content": "ok", "tier": "deep"}
    assert captured["tier"] == "deep"
    assert captured["system"] == "be concise"
    assert captured["user"] == "hello"
    assert captured["maxTokens"] == 42
    assert captured["temperature"] == 0.7


@pytest.mark.asyncio
async def test_task_llm_chat_renders_user_template(monkeypatch):
    """Phase E2: user_template + extra kwargs render the prompt without a
    preceding transform.map step. Mirrors the webmk_create_proposal pattern."""
    import sys, types
    captured = {}

    async def _fake_chat(*, tier, system, user, maxTokens, temperature):
        captured["user"] = user
        return {"content": "rendered"}

    fake = types.ModuleType("kotodama.zeebe_worker_main")
    fake.task_generic_llm_chat = _fake_chat
    monkeypatch.setitem(sys.modules, "kotodama.zeebe_worker_main", fake)

    from kotodama.tools_llm_worker_main import task_llm_chat
    out = await task_llm_chat(
        user_template="Analyze {websiteUrl} in {industry}. Return JSON.",
        websiteUrl="https://acme.example", industry="saas",
    )
    assert out == {"content": "rendered"}
    assert captured["user"] == "Analyze https://acme.example in saas. Return JSON."


@pytest.mark.asyncio
async def test_task_llm_chat_template_missing_keys_render_empty(monkeypatch):
    """Forgiving: missing template vars render to empty string rather than
    blowing up the whole node. The LLM can usually carry on."""
    import sys, types
    captured = {}

    async def _fake_chat(*, tier, system, user, maxTokens, temperature):
        captured["user"] = user
        return {"content": "ok"}

    fake = types.ModuleType("kotodama.zeebe_worker_main")
    fake.task_generic_llm_chat = _fake_chat
    monkeypatch.setitem(sys.modules, "kotodama.zeebe_worker_main", fake)

    from kotodama.tools_llm_worker_main import task_llm_chat
    out = await task_llm_chat(
        user_template="hi {missing} bye",  # nothing supplies `missing`
    )
    assert out == {"content": "ok"}
    assert captured["user"] == "hi  bye"


@pytest.mark.asyncio
async def test_task_llm_chat_user_takes_precedence_over_template(monkeypatch):
    """If both `user` and `user_template` are passed, the literal `user`
    wins — explicit beats implicit."""
    import sys, types
    captured = {}

    async def _fake_chat(*, tier, system, user, maxTokens, temperature):
        captured["user"] = user
        return {"content": "ok"}

    fake = types.ModuleType("kotodama.zeebe_worker_main")
    fake.task_generic_llm_chat = _fake_chat
    monkeypatch.setitem(sys.modules, "kotodama.zeebe_worker_main", fake)

    from kotodama.tools_llm_worker_main import task_llm_chat
    out = await task_llm_chat(
        user="literal prompt",
        user_template="should be {ignored}",
        ignored="X",
    )
    assert out == {"content": "ok"}
    assert captured["user"] == "literal prompt"


@pytest.mark.asyncio
async def test_audit_emit_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.audit.emit" in handlers


@pytest.mark.asyncio
async def test_task_audit_emit_requires_repo_collection_action():
    from kotodama.tools_audit_worker_main import task_audit_emit
    out = await task_audit_emit()
    assert "error" in out
    out2 = await task_audit_emit(repo="did:web:x.etzhayyim.com")
    assert "error" in out2


@pytest.mark.asyncio
async def test_task_audit_emit_returns_vertex_id_and_rkey(monkeypatch):
    """Successful path returns vertexId + rkey, no error. Mocks db_sync to
    avoid real DB. Validates payload threading from inputs to SQL params."""
    import kotodama.tools_audit_worker_main as mod
    import sys, types
    from contextlib import contextmanager

    captured = {}

    class _FakeCursor:
        def execute(self, sql, params):
            captured["sql"] = sql
            captured["params"] = params

    @contextmanager
    def _fake_sync_cursor():
        yield _FakeCursor()

    fake_mod = types.ModuleType("kotodama.db_sync")
    fake_mod.sync_cursor = _fake_sync_cursor
    monkeypatch.setitem(sys.modules, "kotodama.db_sync", fake_mod)

    out = await mod.task_audit_emit(
        repo="did:web:shosha.etzhayyim.com",
        collection="com.etzhayyim.apps.shosha.audit",
        rkey="r-123",
        action="ingest",
        recordJson={"foo": 1},
    )

    assert out["vertexId"] == "did:web:shosha.etzhayyim.com:com.etzhayyim.apps.shosha.audit:r-123:ingest"
    assert out["rkey"] == "r-123"
    assert "error" not in out
    # SQL params order: vertex_id, repo, collection, rkey, action, ts_ms, record_json
    assert captured["params"][1] == "did:web:shosha.etzhayyim.com"
    assert captured["params"][2] == "com.etzhayyim.apps.shosha.audit"
    assert captured["params"][6] == '{"foo":1}'


@pytest.mark.asyncio
async def test_const_echo_registered_in_default_handlers():
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.tools.const.echo" in handlers


@pytest.mark.asyncio
async def test_yoro_canonical_actor_registers_all_methods():
    """ADR-2605082000 Phase A — yoro recovered from NO_TASK_IMPORT spot-check.
    8 methods from kotodama.primitives.yoro_social (multi-line import that
    audit's regex originally missed)."""
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    expected = {
        "com.etzhayyim.apps.yoro.socialPostGraphFallback",
        "com.etzhayyim.apps.yoro.socialPlatformPulseGraphFallback",
        "com.etzhayyim.apps.yoro.socialRespondToMentionGraphFallback",
        "com.etzhayyim.apps.yoro.socialRespondToFollowGraphFallback",
        "com.etzhayyim.apps.yoro.actorQualityInspect",
        "com.etzhayyim.apps.yoro.actorQualityVerify",
        "com.etzhayyim.apps.yoro.actorQualityEnrichProfile",
        "com.etzhayyim.apps.yoro.actorQualityEnsureSeedPost",
    }
    missing = expected - set(handlers.keys())
    assert not missing, f"yoro methods missing: {sorted(missing)}"


@pytest.mark.asyncio
async def test_wellbecoming_process_mining_recovered():
    """processMiningAnalyze added via mapping (iter25 NO_TASK_IMPORT recovery).
    The primitive function is named `analyze` (no task_ prefix) so explicit
    mapping is the right tool."""
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    assert "com.etzhayyim.apps.wellbecoming.processMiningAnalyze" in handlers


@pytest.mark.asyncio
async def test_full_dispatcher_inventory_iter43():
    """ADR-2605082000 Phase A complete inventory snapshot (iter43).
    Catches inadvertent drops in `_DEFAULT_ACTORS` or primitive renames.
    Update this test when a new actor entry lands; it intentionally pins
    the full surface so accidental removal is loud."""
    from kotodama.mcp_dispatch import build_default_handlers
    from collections import Counter

    handlers = build_default_handlers()
    counts = Counter(k.rsplit(".", 1)[0] for k in handlers)

    expected = {
        # actor namespace (com.etzhayyim.apps.<actor>) → method count
        "com.etzhayyim.apps.adsk":           1,
        "com.etzhayyim.apps.agentEconomy":   9,
        "com.etzhayyim.apps.aria":           8,
        "com.etzhayyim.apps.coverageGap":    5,
        "com.etzhayyim.apps.isbn":           6,
        "com.etzhayyim.apps.ki":             4,
        "com.etzhayyim.apps.koke":           5,
        "com.etzhayyim.apps.onion":          2,
        "com.etzhayyim.apps.osMessaging":    2,
        "com.etzhayyim.apps.patent":         3,
        "com.etzhayyim.apps.publicMalakAds": 5,
        "com.etzhayyim.apps.saikin":         5,
        "com.etzhayyim.apps.shinka":         5,
        "com.etzhayyim.apps.shinshi":        3,
        "com.etzhayyim.apps.shosha":         18,
        "com.etzhayyim.apps.wellbecoming":   11,
        "com.etzhayyim.apps.yoro":           8,
        # generic tool primitives (com.etzhayyim.tools.*) — 1 each
        "com.etzhayyim.tools.audit":         1,
        "com.etzhayyim.tools.const":         1,
        "com.etzhayyim.tools.llm":           1,
        "com.etzhayyim.tools.sql":           3,
        "com.etzhayyim.tools.http":          1,
        "com.etzhayyim.tools.json":          1,
        "com.etzhayyim.tools.transform":     1,
        "com.etzhayyim.tools.time":          1,
        "com.etzhayyim.tools.crypto":        1,
    }

    drops = []
    extras = []
    for k, v in expected.items():
        actual = counts.get(k, 0)
        if actual < v:
            drops.append(f"{k}: expected {v}, got {actual}")
    for k in counts:
        if k not in expected:
            extras.append(f"{k}: unexpected actor (got {counts[k]} methods)")

    assert not drops, "Dispatcher actor surface dropped:\n  " + "\n  ".join(drops)
    # Don't fail on extras — they're additive — but surface them in test output
    # so reviewers notice new actor entries.
    if extras:
        import warnings
        warnings.warn(
            "New dispatcher actor(s) detected (update inventory test):\n  "
            + "\n  ".join(extras),
        )

    # Total handler count: keep an eye on the running total. Update when
    # the inventory grows. Currently iter43: 17 actors × N + 3 tools = 103.
    expected_total = sum(expected.values())
    assert len(handlers) >= expected_total, (
        f"Total handler count regressed: got {len(handlers)}, expected ≥ {expected_total}"
    )


@pytest.mark.asyncio
async def test_phase_a_standalone_actors_registered():
    """ADR-2605082000 Phase A — 7 standalone bulk-51 actors fully wired.
    Asserts the per-actor method count to catch primitive-module renames
    that would silently degrade the registry."""
    from kotodama.mcp_dispatch import build_default_handlers
    from collections import Counter
    handlers = build_default_handlers()
    counts = Counter(k.rsplit(".", 1)[0] for k in handlers)
    expected = {
        "com.etzhayyim.apps.agentEconomy": 9,
        "com.etzhayyim.apps.coverageGap": 5,
        "com.etzhayyim.apps.onion": 2,
        "com.etzhayyim.apps.osMessaging": 2,
        "com.etzhayyim.apps.patent": 3,
        "com.etzhayyim.apps.publicMalakAds": 5,
        "com.etzhayyim.apps.shinshi": 3,
    }
    for nsidPrefix, expectedCount in expected.items():
        actual = counts.get(nsidPrefix, 0)
        assert actual == expectedCount, (
            f"{nsidPrefix}: expected {expectedCount} methods, got {actual}. "
            "Primitive module may have renamed task_* fns."
        )


@pytest.mark.asyncio
async def test_wellbecoming_canonical_actor_via_mapping():
    """ADR-2605082000 Phase A — 10-method wellbecoming consolidation across
    4 heterogeneous primitive sub-modules. Uses `mapping` (explicit dict)
    instead of fn_template because the prefix varies (task_wellbecoming_* /
    task_belief_* / task_trust_*)."""
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    expected = {
        "com.etzhayyim.apps.wellbecoming.agentLoop",
        "com.etzhayyim.apps.wellbecoming.bottleneckDetect",
        "com.etzhayyim.apps.wellbecoming.proactiveConnect",
        "com.etzhayyim.apps.wellbecoming.floorCheck",
        "com.etzhayyim.apps.wellbecoming.floorAlert",
        "com.etzhayyim.apps.wellbecoming.minimaxSweep",
        "com.etzhayyim.apps.wellbecoming.beliefInfluencePropagate",
        "com.etzhayyim.apps.wellbecoming.beliefNoiseInject",
        "com.etzhayyim.apps.wellbecoming.beliefRestoringCapture",
        "com.etzhayyim.apps.wellbecoming.trustWeightUpdate",
    }
    missing = expected - set(handlers.keys())
    assert not missing, f"wellbecoming methods missing: {sorted(missing)}"


def test_register_actor_by_mapping_invalid_target_skipped(caplog):
    from kotodama.mcp_dispatch import register_actor_by_mapping
    with caplog.at_level("WARNING", logger="mcp_dispatch"):
        out = register_actor_by_mapping("test", {"foo": "no_colon"})
    assert out == {}
    assert any("missing ':<fn>'" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_isbn_canonical_actor_registers_all_methods():
    """ADR-2605082000 Phase A — 6-source isbn consolidation."""
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    expected = {
        "com.etzhayyim.apps.isbn.aozoraIngest",
        "com.etzhayyim.apps.isbn.gutenbergIngest",
        "com.etzhayyim.apps.isbn.ndlIngest",
        "com.etzhayyim.apps.isbn.hathitrustIngest",
        "com.etzhayyim.apps.isbn.internetArchiveIngest",
        "com.etzhayyim.apps.isbn.openLibraryIngest",
    }
    missing = expected - set(handlers.keys())
    assert not missing, f"isbn methods missing: {sorted(missing)}"


@pytest.mark.asyncio
async def test_shosha_canonical_actor_registers_all_methods():
    """ADR-2605082000 Phase A — 18-method shosha consolidation. Method
    surface is derived from `kotodama.primitives.shosha:task_shosha_*`
    (not bulk-51 inferred names) so the template `task_shosha_{snake}`
    resolves cleanly without per-method overrides."""
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    expected = {
        "com.etzhayyim.apps.shosha.intelIngestPrices",
        "com.etzhayyim.apps.shosha.intelIngestFreight",
        "com.etzhayyim.apps.shosha.marketViewSynth",
        "com.etzhayyim.apps.shosha.sanctionsRefreshOfac",
        "com.etzhayyim.apps.shosha.sanctionsRefreshUn",
        "com.etzhayyim.apps.shosha.complySanctionsCheck",
        "com.etzhayyim.apps.shosha.tradeSubmit",
        "com.etzhayyim.apps.shosha.exposureRecompute",
        "com.etzhayyim.apps.shosha.pnlDailyRecompute",
        "com.etzhayyim.apps.shosha.tradeSynth",
        "com.etzhayyim.apps.shosha.tradeSettle",
        "com.etzhayyim.apps.shosha.tradeApprove",
        "com.etzhayyim.apps.shosha.tradeReject",
        "com.etzhayyim.apps.shosha.hedgePropose",
        "com.etzhayyim.apps.shosha.dailyReportCompose",
        "com.etzhayyim.apps.shosha.agentChat",
        "com.etzhayyim.apps.shosha.reactiveScanUpstream",
        "com.etzhayyim.apps.shosha.coverageSnapshot",
    }
    missing = expected - set(handlers.keys())
    assert not missing, (
        f"shosha methods missing: {sorted(missing)}. "
        "Check kotodama.primitives.shosha for renamed task_shosha_* fns."
    )


@pytest.mark.asyncio
async def test_aria_canonical_actor_registers_all_methods():
    """ADR-2605082000 Phase A canonical-actor consolidation: 7+1 aria
    methods register cleanly via the override convention. Catches
    regressions in kotodama.primitives.aria_signal renames."""
    from kotodama.mcp_dispatch import build_default_handlers
    handlers = build_default_handlers()
    expected = {
        "com.etzhayyim.apps.aria.attentionIngest",
        "com.etzhayyim.apps.aria.emotionIngest",
        "com.etzhayyim.apps.aria.influenceIngest",
        "com.etzhayyim.apps.aria.marketDeltaIngest",
        "com.etzhayyim.apps.aria.minimaxSweep",
        "com.etzhayyim.apps.aria.moneyFlowIngest",
        "com.etzhayyim.apps.aria.requestIngest",
        "com.etzhayyim.apps.aria.reverseTopoReplan",
    }
    missing = expected - set(handlers.keys())
    assert not missing, (
        f"aria methods missing from default handlers: {sorted(missing)}. "
        "Check kotodama.primitives.aria_signal for renamed task_aria_* fns."
    )


@pytest.mark.asyncio
async def test_handler_must_return_dict():
    from kotodama.mcp_dispatch import handle_envelope

    async def _bad(**_):
        return ["not", "a", "dict"]  # type: ignore[return-value]

    handlers = {"com.etzhayyim.apps.saikin.probeEnvironment": _bad}
    status, body = await handle_envelope(
        {
            "method": "tools/call",
            "params": {"name": "com.etzhayyim.apps.saikin.probeEnvironment", "arguments": {}},
        },
        handlers,
    )

    assert status == 500
    assert "must return dict" in body["error"]
