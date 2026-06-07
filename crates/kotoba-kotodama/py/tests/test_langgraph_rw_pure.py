"""
Pure unit tests for RisingWaveCheckpointSaver and RisingWaveStore.
No RisingWave connection required — DB calls are mocked.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch, NonCallableMagicMock

import pytest

from kotodama.langgraph_checkpoint_rw import (
    RisingWaveCheckpointSaver,
    _checkpoint_pk,
    _deserialize,
    _serialize,
    _write_pk,
)
from kotodama.langgraph_store_rw import RisingWaveStore, _ns_str, _pk, _row_to_item


# ─────────────────────────────────────────────────────────────── helpers ──

def _make_checkpoint(checkpoint_id: str = "cid001") -> dict:
    return {"id": checkpoint_id, "v": 1, "ts": "2026-05-07T00:00:00Z", "channel_values": {}, "channel_versions": {}, "versions_seen": {}}


def _make_config(thread_id: str = "t1", checkpoint_ns: str = "", checkpoint_id: str | None = None) -> dict:
    cfg: dict = {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}
    if checkpoint_id:
        cfg["checkpoint_id"] = checkpoint_id
    return {"configurable": cfg}


# ──────────────────────────────────────────────────── pk helpers ──

def test_checkpoint_pk():
    assert _checkpoint_pk("t1", "", "cid1") == "t1::cid1"
    assert _checkpoint_pk("t1", "sub", "cid1") == "t1:sub:cid1"


def test_write_pk():
    assert _write_pk("t1", "", "cid1", "task1", 0) == "t1::cid1:task1:0"


# ──────────────────────────────────────────────────── serialize ──

def test_serialize_roundtrip():
    cp = _make_checkpoint()
    meta = {"source": "input", "step": 0, "writes": None, "parents": {}}
    blob = _serialize(cp, meta)
    cp2, meta2 = _deserialize(blob)
    assert cp2["id"] == cp["id"]
    assert meta2["step"] == 0


# ──────────────────────────────────── RisingWaveCheckpointSaver ──

@pytest.mark.asyncio
async def test_aput_inserts_row():
    saver = RisingWaveCheckpointSaver()
    cp = _make_checkpoint("cid-abc")
    config = _make_config("thread1")
    meta = {"source": "input", "step": 0, "writes": None, "parents": {}}

    mock_cur = AsyncMock()
    with patch("kotodama.langgraph_checkpoint_rw._cursor") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await saver.aput(config, cp, meta, {})

    assert result["configurable"]["thread_id"] == "thread1"
    assert result["configurable"]["checkpoint_id"] == "cid-abc"
    mock_cur.execute.assert_called_once()
    sql_called = mock_cur.execute.call_args[0][0]
    assert "INSERT INTO vertex_langgraph_checkpoint" in sql_called


@pytest.mark.asyncio
async def test_aput_writes_inserts_rows():
    saver = RisingWaveCheckpointSaver()
    config = _make_config("t1", "", "cid1")
    writes = [("channel_a", {"value": 1}), ("channel_b", "text")]

    mock_cur = AsyncMock()
    with patch("kotodama.langgraph_checkpoint_rw._cursor") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        await saver.aput_writes(config, writes, "task-x")

    assert mock_cur.execute.call_count == 2
    sql_first = mock_cur.execute.call_args_list[0][0][0]
    assert "INSERT INTO vertex_langgraph_checkpoint_write" in sql_first


@pytest.mark.asyncio
async def test_aget_tuple_returns_none_when_not_found():
    saver = RisingWaveCheckpointSaver()
    config = _make_config("t1", "", "nonexistent")

    mock_cur = AsyncMock()
    mock_cur.fetchone = AsyncMock(return_value=None)
    with patch("kotodama.langgraph_checkpoint_rw._cursor") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await saver.aget_tuple(config)

    assert result is None


@pytest.mark.asyncio
async def test_aget_tuple_returns_tuple_when_found():
    saver = RisingWaveCheckpointSaver()
    config = _make_config("t1", "", "cid1")

    cp = _make_checkpoint("cid1")
    meta = {"source": "input", "step": 1, "writes": None, "parents": {}}
    blob = _serialize(cp, meta)

    mock_cur = AsyncMock()
    mock_cur.fetchone = AsyncMock(return_value=("t1::cid1", "t1", "cid1", "", None, "json", blob))
    mock_cur.fetchall = AsyncMock(return_value=[])
    with patch("kotodama.langgraph_checkpoint_rw._cursor") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await saver.aget_tuple(config)

    assert result is not None
    assert result.checkpoint["id"] == "cid1"
    assert result.config["configurable"]["thread_id"] == "t1"


@pytest.mark.asyncio
async def test_adelete_thread_executes_deletes():
    saver = RisingWaveCheckpointSaver()

    mock_cur = AsyncMock()
    with patch("kotodama.langgraph_checkpoint_rw._cursor") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        await saver.adelete_thread("t1")

    assert mock_cur.execute.call_count == 2
    sqls = [call[0][0] for call in mock_cur.execute.call_args_list]
    assert any("vertex_langgraph_checkpoint_write" in s for s in sqls)
    assert any("vertex_langgraph_checkpoint" in s and "write" not in s for s in sqls)


def test_get_next_version():
    saver = RisingWaveCheckpointSaver()
    assert saver.get_next_version(None, None) == 1
    assert saver.get_next_version(3, None) == 4


# ──────────────────────────────────────────── RisingWaveStore ──

def test_ns_str():
    assert _ns_str(("actor", "memory")) == "actor/memory"
    assert _ns_str(()) == ""


def test_pk():
    assert _pk(("a", "b"), "k1") == "a/b:k1"


def test_row_to_item():
    import datetime
    now = "2026-05-07T00:00:00+00:00"
    row = ("a/b:k1", "a/b", "k1", '{"x": 1}', now, now)
    item = _row_to_item(row)
    assert item.key == "k1"
    assert item.namespace == ("a", "b")
    assert item.value == {"x": 1}


def _make_store_mocks(mock_cur: AsyncMock):
    """Build pool/conn/cursor mock chain for RisingWaveStore.abatch tests."""
    # cursor context manager
    mock_cursor_ctx = MagicMock()
    mock_cursor_ctx.__aenter__ = AsyncMock(return_value=mock_cur)
    mock_cursor_ctx.__aexit__ = AsyncMock(return_value=False)

    # connection context manager
    mock_conn = MagicMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.cursor = MagicMock(return_value=mock_cursor_ctx)

    # pool
    mock_pool = MagicMock()
    mock_pool.closed = False
    mock_pool.connection = MagicMock(return_value=mock_conn)
    return mock_pool


@pytest.mark.asyncio
async def test_abatch_get_returns_item():
    store = RisingWaveStore()
    now = "2026-05-07T00:00:00+00:00"
    row = ("actor/mem:k1", "actor/mem", "k1", '{"score": 99}', now, now)

    mock_cur = AsyncMock()
    mock_cur.fetchone = AsyncMock(return_value=row)
    mock_pool = _make_store_mocks(mock_cur)

    from langgraph.store.base import GetOp
    op = GetOp(namespace=("actor", "mem"), key="k1", refresh_ttl=False)

    with patch("kotodama.langgraph_store_rw._ensure_pool", AsyncMock(return_value=mock_pool)):
        results = await store.abatch([op])

    assert len(results) == 1
    item = results[0]
    assert item is not None
    assert item.key == "k1"
    assert item.value == {"score": 99}


@pytest.mark.asyncio
async def test_abatch_put_none_deletes():
    store = RisingWaveStore()

    mock_cur = AsyncMock()
    mock_pool = _make_store_mocks(mock_cur)

    from langgraph.store.base import PutOp
    op = PutOp(namespace=("actor", "mem"), key="k1", value=None, index=None, ttl=None)

    with patch("kotodama.langgraph_store_rw._ensure_pool", AsyncMock(return_value=mock_pool)):
        await store.abatch([op])

    mock_cur.execute.assert_called_once()
    assert "DELETE FROM vertex_langgraph_store" in mock_cur.execute.call_args[0][0]
