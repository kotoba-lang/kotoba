"""Unit tests for the kotoba-native LangGraph checkpoint saver (RW-free).

Covers the pure pack/unpack content-addressing + entity-builder + query helpers.
The saver class itself needs langgraph at runtime; these helpers are langgraph-free
so they exercise the substrate mapping in isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama import langgraph_checkpoint_kotoba as cp


def test_pack_small_payload_is_plaintext() -> None:
    blob, cid, comp, logical, stored = cp._pack({"id": "C", "v": 1}, {"step": 3})
    assert comp == "none"
    assert stored == logical
    assert len(cid) == 64  # sha256 hex


def test_pack_large_payload_is_zlib_b64() -> None:
    big = {"id": "B", "channel_values": {"blob": "A" * 5000}}
    blob, cid, comp, logical, stored = cp._pack(big, {})
    assert comp == "zlib-b64"
    assert stored < logical  # compression actually saved bytes


def test_pack_unpack_round_trip() -> None:
    checkpoint = {"id": "01CKP", "channel_values": {"x": 1}}
    metadata = {"source": "loop", "step": 3}
    blob, cid, comp, _, _ = cp._pack(checkpoint, metadata)
    assert cp._unpack(blob, comp) == (checkpoint, metadata)


def test_pack_is_content_addressed_deterministic() -> None:
    a = cp._pack({"id": "C"}, {"m": 1})[1]
    b = cp._pack({"id": "C"}, {"m": 1})[1]
    assert a == b  # identical content → identical cid → kotoba dedup


def test_pk_builders() -> None:
    assert cp._checkpoint_pk("T", "NS", "C") == "T:NS:C"
    assert cp._write_pk("T", "", "C", "task9", 2) == "T::C:task9:2"


def test_checkpoint_entity_drops_none_parent() -> None:
    ce = cp._checkpoint_entity("T:NS:C", "T", "C", "NS", None, "cid", "none", 10, "NOW")
    assert ce[":lg.checkpoint/vertex-id"] == "T:NS:C"
    assert ":lg.checkpoint/parent-checkpoint-id" not in ce
    ce2 = cp._checkpoint_entity("T:NS:C", "T", "C", "NS", "PARENT", "cid", "none", 10, "NOW")
    assert ce2[":lg.checkpoint/parent-checkpoint-id"] == "PARENT"


def test_blob_and_write_entities() -> None:
    be = cp._blob_entity("cid", "blob", "none", 10, 10, "NOW")
    assert be[":lg.checkpoint-blob/vertex-id"] == "cid"
    we = cp._write_entity("WPK", "T", "C", "NS", "task9", "", 2, "ch", "{}", "NOW")
    assert we[":lg.checkpoint-write/idx"] == 2
    assert we[":lg.checkpoint-write/type"] == "json"


def test_pull_query_and_strip_ns() -> None:
    q = cp._pull_by_attr_query(cp.NS_CP, "thread-id", "T")
    assert q == '[:find (pull ?e [*]) :where [?e :lg.checkpoint/thread-id "T"]]'
    stripped = cp._strip_ns(
        {":lg.checkpoint/thread-id": "T", ":lg.checkpoint/checkpoint-id": "C"}, cp.NS_CP
    )
    assert stripped == {"thread_id": "T", "checkpoint_id": "C"}
