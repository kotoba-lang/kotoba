"""MstCheckpointSaver tests against an in-memory mock sidecar.

Verifies the wire protocol contract (ADR-2605171800 §Stage 1):
  - 4-byte big-endian length prefix
  - msgpack envelope { v=1, op, cell_did, thread_id, checkpoint_ns, checkpoint_id, payload, meta }
  - Response { ok, mst_root_cid, data, error }
  - put / get_tuple / list / put_writes round-trips
  - Health probe
  - Async API parity
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from kotodama.checkpointer import (
    MST_CHECKPOINT_PROTOCOL_VERSION,
    MstCheckpointSaver,
    MstCheckpointSaverError,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _saver(mock_sidecar) -> MstCheckpointSaver:
    return MstCheckpointSaver(
        cell_did="did:test:uhl-pregel",
        socket_path=mock_sidecar.url,
    )


def _config(thread_id: str = "t-1", checkpoint_id: str | None = None) -> dict:
    cfg = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    if checkpoint_id is not None:
        cfg["configurable"]["checkpoint_id"] = checkpoint_id
    return cfg


def _checkpoint(cp_id: str, channel: str = "ch1", val: int = 1) -> dict:
    return {
        "v": 1,
        "id": cp_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "channel_values": {channel: val},
        "channel_versions": {channel: "1"},
        "versions_seen": {},
        "updated_channels": [channel],
    }


# ── Tests ────────────────────────────────────────────────────────────────────


def test_health_round_trip(mock_sidecar):
    saver = _saver(mock_sidecar)
    resp = saver.health()
    assert resp["ok"] is True
    assert mock_sidecar.requests[-1]["v"] == MST_CHECKPOINT_PROTOCOL_VERSION
    assert mock_sidecar.requests[-1]["op"] == "health"
    assert mock_sidecar.requests[-1]["cell_did"] == "did:test:uhl-pregel"


def test_cell_did_validation():
    with pytest.raises(ValueError, match="must be a DID"):
        MstCheckpointSaver(cell_did="not-a-did")


def test_put_then_get_tuple_round_trip(mock_sidecar):
    saver = _saver(mock_sidecar)
    cfg = _config("t-1")
    cp = _checkpoint("1ckp001", channel="alpha", val=42)
    metadata = {"source": "loop", "step": 1, "parents": {}}
    versions = {"alpha": "1"}

    out_config = saver.put(cfg, cp, metadata, versions)
    assert out_config["configurable"]["thread_id"] == "t-1"
    assert out_config["configurable"]["checkpoint_id"] == "1ckp001"

    tup = saver.get_tuple(_config("t-1"))
    assert tup is not None
    assert tup.checkpoint["id"] == "1ckp001"
    assert tup.checkpoint["channel_values"] == {"alpha": 42}
    assert tup.metadata.get("step") == 1
    assert tup.parent_config is None  # first checkpoint has no parent


def test_get_tuple_returns_none_when_empty(mock_sidecar):
    saver = _saver(mock_sidecar)
    tup = saver.get_tuple(_config("nonexistent-thread"))
    assert tup is None


def test_parent_chain_via_two_puts(mock_sidecar):
    saver = _saver(mock_sidecar)
    saver.put(_config("t-2"), _checkpoint("1ckp001"), {"step": 1}, {"ch1": "1"})
    saver.put(_config("t-2"), _checkpoint("1ckp002"), {"step": 2}, {"ch1": "2"})

    latest = saver.get_tuple(_config("t-2"))
    assert latest is not None
    assert latest.checkpoint["id"] == "1ckp002"
    assert latest.parent_config is not None
    assert latest.parent_config["configurable"]["checkpoint_id"] == "1ckp001"


def test_get_tuple_with_explicit_checkpoint_id(mock_sidecar):
    saver = _saver(mock_sidecar)
    saver.put(_config("t-3"), _checkpoint("1ckp001"), {"step": 1}, {"ch1": "1"})
    saver.put(_config("t-3"), _checkpoint("1ckp002"), {"step": 2}, {"ch1": "2"})

    older = saver.get_tuple(_config("t-3", checkpoint_id="1ckp001"))
    assert older is not None
    assert older.checkpoint["id"] == "1ckp001"


def test_list_returns_newest_first(mock_sidecar):
    saver = _saver(mock_sidecar)
    for i in range(3):
        cp_id = f"1ckp00{i+1}"
        saver.put(_config("t-4"), _checkpoint(cp_id), {"step": i + 1}, {"ch1": str(i + 1)})

    tuples = list(saver.list(_config("t-4")))
    assert [t.checkpoint["id"] for t in tuples] == ["1ckp003", "1ckp002", "1ckp001"]


def test_list_limit_truncates(mock_sidecar):
    saver = _saver(mock_sidecar)
    for i in range(5):
        cp_id = f"1ckp00{i+1}"
        saver.put(_config("t-5"), _checkpoint(cp_id), {"step": i + 1}, {"ch1": str(i + 1)})

    tuples = list(saver.list(_config("t-5"), limit=2))
    assert len(tuples) == 2
    assert [t.checkpoint["id"] for t in tuples] == ["1ckp005", "1ckp004"]


def test_put_writes(mock_sidecar):
    saver = _saver(mock_sidecar)
    saver.put(_config("t-6"), _checkpoint("1ckp001"), {"step": 1}, {"ch1": "1"})

    saver.put_writes(
        _config("t-6", checkpoint_id="1ckp001"),
        writes=[("ch1", "value-a"), ("ch1", "value-b")],
        task_id="task-1",
    )
    pw_requests = [r for r in mock_sidecar.requests if r["op"] == "put_writes"]
    assert len(pw_requests) == 1
    assert pw_requests[0]["checkpoint_id"] == "1ckp001"
    assert pw_requests[0]["meta"]["task_id"] == "task-1"


def test_put_writes_requires_checkpoint_id(mock_sidecar):
    saver = _saver(mock_sidecar)
    with pytest.raises(ValueError, match="checkpoint_id.*required"):
        saver.put_writes(_config("t-7"), writes=[("ch1", "v")], task_id="task-1")


def test_sidecar_failure_raises(mock_sidecar):
    saver = _saver(mock_sidecar)
    mock_sidecar.fail_next("put")
    with pytest.raises(MstCheckpointSaverError, match="injected failure"):
        saver.put(_config("t-8"), _checkpoint("1ckp001"), {"step": 1}, {"ch1": "1"})


def test_envelope_contains_required_fields(mock_sidecar):
    saver = _saver(mock_sidecar)
    saver.put(_config("t-9"), _checkpoint("1ckp001"), {"step": 1}, {"ch1": "1"})
    req = mock_sidecar.requests[-1]
    assert set(req.keys()) >= {
        "v",
        "op",
        "cell_did",
        "thread_id",
        "checkpoint_ns",
        "checkpoint_id",
        "payload",
        "meta",
    }
    assert req["v"] == 1
    assert req["cell_did"] == "did:test:uhl-pregel"
    assert req["thread_id"] == "t-9"


def test_thread_id_required(mock_sidecar):
    saver = _saver(mock_sidecar)
    with pytest.raises(ValueError, match="thread_id"):
        saver.put({"configurable": {}}, _checkpoint("1ckp001"), {"step": 1}, {"ch1": "1"})


# ── Async parity ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aput_then_aget_tuple(mock_sidecar):
    saver = _saver(mock_sidecar)
    await saver.aput(_config("a-1"), _checkpoint("1ckp001"), {"step": 1}, {"ch1": "1"})
    tup = await saver.aget_tuple(_config("a-1"))
    assert tup is not None
    assert tup.checkpoint["id"] == "1ckp001"


@pytest.mark.asyncio
async def test_alist_returns_newest_first(mock_sidecar):
    saver = _saver(mock_sidecar)
    for i in range(3):
        await saver.aput(_config("a-2"), _checkpoint(f"1ckp00{i+1}"), {"step": i + 1}, {"ch1": str(i + 1)})
    seen = []
    async for tup in saver.alist(_config("a-2")):
        seen.append(tup.checkpoint["id"])
    assert seen == ["1ckp003", "1ckp002", "1ckp001"]


@pytest.mark.asyncio
async def test_ahealth(mock_sidecar):
    saver = _saver(mock_sidecar)
    resp = await saver.ahealth()
    assert resp["ok"] is True
    await saver.aclose()
