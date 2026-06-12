"""Pure unit tests for the _pack / _unpack codec in langgraph_checkpoint_rw.

No DB, no langgraph runtime — exercises only the Shannon source-coding layer.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("langgraph", reason="langgraph not installed in this env")

from kotodama.langgraph_checkpoint_rw import _pack, _unpack, _COMPRESS_MIN_BYTES


def test_pack_small_payload_stays_plain() -> None:
    cp = {"id": "c1", "channels": {"messages": ["hi"]}}
    md = {"step": 1}
    blob, cid, compression, logical, stored = _pack(cp, md)
    assert compression == "none"
    assert logical == stored == len(blob.encode("utf-8"))
    # plain JSON must round-trip via json.loads
    parsed = json.loads(blob)
    assert parsed["checkpoint"] == cp
    assert parsed["metadata"] == md
    assert len(cid) == 64  # sha256 hex


def test_pack_large_payload_compresses() -> None:
    cp = {"id": "c1", "channels": {"messages": ["x" * (_COMPRESS_MIN_BYTES * 4)]}}
    md = {"step": 2}
    blob, cid, compression, logical, stored = _pack(cp, md)
    assert compression == "zlib-b64"
    assert stored < logical
    # round-trip
    cp2, md2 = _unpack(blob, compression)
    assert cp2 == cp
    assert md2 == md


def test_unpack_handles_legacy_none_compression() -> None:
    cp = {"id": "legacy", "channels": {}}
    md = {"step": 0}
    plain = json.dumps({"checkpoint": cp, "metadata": md})
    cp2, md2 = _unpack(plain, None)
    assert cp2 == cp
    assert md2 == md


def test_pack_is_content_addressed_deterministic() -> None:
    cp = {"id": "c1", "channels": {"a": 1, "b": 2}}
    md = {"step": 1}
    _, cid_a, *_ = _pack(cp, md)
    _, cid_b, *_ = _pack({"id": "c1", "channels": {"b": 2, "a": 1}}, md)
    assert cid_a == cid_b, "sort_keys=True must make CID order-independent"
