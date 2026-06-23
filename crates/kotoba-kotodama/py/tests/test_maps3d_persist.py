"""Datom-log persistence tests for the maps3d pipeline.

Covers the gap closed in this change: the photogrammetry pipeline computed
detections + actor links but never landed them in the kotoba Datom log, even
though processTile.bpmn's "mark tile done" step documents that the worker tasks
"have already INSERT-ed into vertex_vision_result / edge_*". These tests assert
the helpers now upsert via the kotoba Datomic client (ADR-2605262130) and that
the prior linkActor registry-read bug (SELECT string → Datalog q(), empty cols)
is fixed to use the Datalog-backed select shim.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import maps3d as M


class _FakeClient:
    """Records insert_row upserts and serves a canned select_where result."""

    def __init__(self, registry_rows=None):
        self.inserts: list[tuple[str, dict]] = []
        self._registry_rows = registry_rows or []
        self.select_calls: list[tuple] = []

    def insert_row(self, table, row):
        self.inserts.append((table, dict(row)))
        return {"datom_count": len(row)}

    def select_where(self, table, column, value, columns=(), *, limit=100):
        self.select_calls.append((table, column, value, tuple(columns), limit))
        return list(self._registry_rows)


# ─── _stable_rkey ───────────────────────────────────────────────────────────

def test_stable_rkey_is_deterministic_and_collision_resistant():
    a = M._stable_rkey("tileX", "Starbucks", "img1")
    assert a == M._stable_rkey("tileX", "Starbucks", "img1")  # idempotent
    assert a != M._stable_rkey("tileX", "Starbucks", "img2")  # field-sensitive
    assert len(a) == 16


# ─── _persist_vision_results ─────────────────────────────────────────────────

def test_persist_vision_results_upserts_each_detection():
    fake = _FakeClient()
    detections = [
        {"label": "Starbucks", "confidence": 0.9, "category": "business", "imageRef": "img1"},
        {"label": "Tower", "confidence": 0.8, "category": "landmark", "imageRef": "img2"},
    ]
    with patch.object(M, "get_kotoba_client", return_value=fake):
        n = M._persist_vision_results("tile-h3-abc", detections)

    assert n == 2
    assert {t for t, _ in fake.inserts} == {"vertex_vision_result"}
    first = fake.inserts[0][1]
    assert first["tile_h3"] == "tile-h3-abc"
    assert first["label"] == "Starbucks"
    assert first["vertex_id"].startswith("at://did:web:maps.etzhayyim.com/")


def test_persist_vision_results_is_idempotent_across_reruns():
    fake = _FakeClient()
    dets = [{"label": "Cafe", "confidence": 0.7, "imageRef": "imgA"}]
    with patch.object(M, "get_kotoba_client", return_value=fake):
        M._persist_vision_results("t1", dets)
        M._persist_vision_results("t1", dets)
    # same vertex_id both times → re-transact upserts (unique/identity), no dup id
    ids = [row["vertex_id"] for _, row in fake.inserts]
    assert len(ids) == 2 and ids[0] == ids[1]


def test_persist_vision_results_skips_blank_labels_and_empty_input():
    fake = _FakeClient()
    with patch.object(M, "get_kotoba_client", return_value=fake):
        assert M._persist_vision_results("t1", [{"label": "  "}]) == 0
        assert M._persist_vision_results("t1", []) == 0
        assert M._persist_vision_results("", [{"label": "X"}]) == 0
    assert fake.inserts == []


def test_persist_vision_results_fails_open_on_substrate_error():
    class _Boom(_FakeClient):
        def insert_row(self, table, row):
            raise RuntimeError("kotoba node down")

    with patch.object(M, "get_kotoba_client", return_value=_Boom()):
        # must not raise — pipeline task stays alive (kotoba-first/fail-open)
        assert M._persist_vision_results("t1", [{"label": "X"}]) == 0


# ─── _persist_actor_links ────────────────────────────────────────────────────

def test_persist_actor_links_upserts_edges():
    fake = _FakeClient()
    links = [
        {"label": "Starbucks", "actorDid": "did:web:maps.etzhayyim.com:registry:wikidata:Q38076",
         "confidence": 0.95, "source": "wikidata"},
        {"label": "NoDid", "actorDid": "", "confidence": 0.99},  # dropped: no DID
    ]
    with patch.object(M, "get_kotoba_client", return_value=fake):
        n = M._persist_actor_links("tile-9", links)

    assert n == 1
    table, row = fake.inserts[0]
    assert table == "edge_maps3d_actor_link"
    assert row["actor_did"].endswith("Q38076")
    assert row["source"] == "wikidata"


# ─── registry-read bug fix (linkActor) ───────────────────────────────────────

def test_link_actor_uses_select_shim_not_sql_string():
    fake = _FakeClient(registry_rows=[{"did": "did:web:x", "handle": "x", "display_name": "X"}])
    # Force the LLM path to fail so we exercise only the registry read + return,
    # without needing a live Murakumo backend.
    with patch.object(M, "get_kotoba_client", return_value=fake), \
         patch.object(M._llm, "call_tier_json", side_effect=RuntimeError("no llm")):
        out = asyncio.run(M.task_maps3d_link_actor(
            tileH3="tile-1",
            detections=[{"label": "Starbucks"}],
        ))

    assert out["ok"] is True
    # the fix routes through select_where on the vertex_actor_registry table
    assert fake.select_calls, "registry read must use the Datalog select shim"
    table, column, value, _cols, _limit = fake.select_calls[0]
    assert (table, column, value) == ("vertex_actor_registry", "status", "active")
