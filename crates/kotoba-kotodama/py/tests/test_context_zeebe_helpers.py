"""Tests for pure helpers in context.py and ingest/zeebe.py compatibility."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.context import Context, _UnwiredDb
from kotodama.ingest.zeebe import start_process_if_configured


# ─── context._UnwiredDb ──────────────────────────────────────────────────────

def test_unwireddb_fetchrow_raises_not_implemented() -> None:
    import asyncio
    db = _UnwiredDb()
    try:
        asyncio.run(db.fetchrow("SELECT 1"))
        assert False, "expected NotImplementedError"
    except NotImplementedError as exc:
        assert "not wired" in str(exc).lower() or "kotodama" in str(exc)


def test_unwireddb_fetch_raises_not_implemented() -> None:
    import asyncio
    db = _UnwiredDb()
    try:
        asyncio.run(db.fetch("SELECT 1"))
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass


def test_unwireddb_execute_raises_not_implemented() -> None:
    import asyncio
    db = _UnwiredDb()
    try:
        asyncio.run(db.execute("UPDATE x SET y = 1"))
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass


def test_unwireddb_executemany_raises_not_implemented() -> None:
    import asyncio
    db = _UnwiredDb()
    try:
        asyncio.run(db.executemany("INSERT INTO x VALUES ($1)", []))
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass


# ─── context.Context ─────────────────────────────────────────────────────────

def test_context_stores_nsid() -> None:
    ctx = Context("com.etzhayyim.apps.test.doThing")
    assert ctx.nsid == "com.etzhayyim.apps.test.doThing"


def test_context_db_is_unwireddb_instance() -> None:
    ctx = Context("some.nsid")
    assert isinstance(ctx.db, _UnwiredDb)


def test_context_logger_returns_logger() -> None:
    import logging
    ctx = Context("com.etzhayyim.apps.mymod.action")
    logger = ctx.logger()
    assert isinstance(logger, logging.Logger)


def test_context_logger_name_contains_nsid() -> None:
    ctx = Context("com.etzhayyim.apps.mymod.myAction")
    assert "com.etzhayyim.apps.mymod.myAction" in ctx.logger().name


def test_context_two_instances_have_different_loggers() -> None:
    ctx_a = Context("com.etzhayyim.apps.x.a")
    ctx_b = Context("com.etzhayyim.apps.x.b")
    assert ctx_a.logger().name != ctx_b.logger().name


def test_context_empty_nsid_allowed() -> None:
    ctx = Context("")
    assert ctx.nsid == ""


# ─── ingest/zeebe.start_process_if_configured ────────────────────────────────

def test_start_process_disabled(monkeypatch) -> None:
    monkeypatch.setenv("INGEST_LANGSERVER_DISABLED", "1")
    key, err = start_process_if_configured("my.process", {})
    assert key is None
    assert err is not None
    assert "INGEST_LANGSERVER_DISABLED" in err


def test_start_process_empty_agentgateway_env(monkeypatch) -> None:
    monkeypatch.delenv("INGEST_LANGSERVER_DISABLED", raising=False)
    monkeypatch.setenv("AGENTGATEWAY_MCP_URL", "http://127.0.0.1:9")
    key, err = start_process_if_configured("my.process", {})
    assert key is None
    assert err is not None


def test_start_process_with_agentgateway_failure(monkeypatch) -> None:
    monkeypatch.delenv("INGEST_LANGSERVER_DISABLED", raising=False)
    monkeypatch.setenv("AGENTGATEWAY_MCP_URL", "http://127.0.0.1:9")
    key, err = start_process_if_configured("my.process", {"var": "val"})
    assert isinstance(key, (str, type(None)))
    assert isinstance(err, (str, type(None)))


def test_start_process_returns_two_tuple(monkeypatch) -> None:
    monkeypatch.setenv("INGEST_LANGSERVER_DISABLED", "1")
    result = start_process_if_configured("proc.id", {})
    assert len(result) == 2


def test_start_process_key_is_none_when_error(monkeypatch) -> None:
    monkeypatch.setenv("INGEST_LANGSERVER_DISABLED", "1")
    key, err = start_process_if_configured("x", {})
    assert key is None
    assert err  # non-empty string
