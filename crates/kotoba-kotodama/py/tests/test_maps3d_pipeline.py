"""Success / parse-path tests for the maps3d Python task bodies.

The earlier suites (test_maps3d_tasks.py) covered the guard branches; this covers
the network/LLM SUCCESS paths with mocked I/O (no COLMAP / Mapillary / Murakumo):
the COLMAP + simplify poll loops, vision JSON-from-LLM parsing + dedup, and link
disambiguation parsing + persistence. Keeps the Python side at parity with the
Clojure reimplementation (maps3d_net_tasks.cljc).
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


def _run(coro):
    return asyncio.run(coro)


# ─── colmapTile poll loop ─────────────────────────────────────────────────────

def test_colmap_poll_done():
    with patch.object(M, "_http_post", return_value={"jobId": "j1"}), \
         patch.object(M, "_http_get", return_value={"status": "done", "rawMeshUri": "ipfs://m", "imageCount": 12}), \
         patch.object(M.time, "sleep", lambda *_: None):
        out = _run(M.task_maps3d_colmap_tile(tileH3="t", selectedIds=["a", "b"],
                                             imageUrls=[{"id": "a", "thumbUrl": "u"}]))
    assert out["ok"] is True
    assert out["rawMeshUri"] == "ipfs://m"
    assert out["imageCount"] == 12


def test_colmap_poll_failed():
    with patch.object(M, "_http_post", return_value={"job_id": "j1"}), \
         patch.object(M, "_http_get", return_value={"status": "failed", "errorCode": "DEGENERATE", "imageCount": 3}), \
         patch.object(M.time, "sleep", lambda *_: None):
        out = _run(M.task_maps3d_colmap_tile(tileH3="t", selectedIds=["a"]))
    assert out["ok"] is False
    assert out["errorCode"] == "DEGENERATE"
    assert out["imageCount"] == 3


def test_colmap_poll_timeout():
    with patch.object(M, "_http_post", return_value={"jobId": "j1"}), \
         patch.object(M, "_http_get", return_value={"status": "running"}), \
         patch.object(M.time, "sleep", lambda *_: None), \
         patch.object(M, "_COLMAP_MAX_POLLS", 3):
        out = _run(M.task_maps3d_colmap_tile(tileH3="t", selectedIds=["a"]))
    assert out["errorCode"] == "POLL_TIMEOUT"


def test_colmap_transient_get_error_keeps_polling():
    calls = {"n": 0}

    def flaky_get(*_a, **_k):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return {"status": "done", "rawMeshUri": "ipfs://m"}

    with patch.object(M, "_http_post", return_value={"jobId": "j1"}), \
         patch.object(M, "_http_get", side_effect=flaky_get), \
         patch.object(M.time, "sleep", lambda *_: None):
        out = _run(M.task_maps3d_colmap_tile(tileH3="t", selectedIds=["a"]))
    assert out["ok"] is True


# ─── simplifyAndExport poll loop ──────────────────────────────────────────────

def test_simplify_poll_done():
    with patch.object(M, "_http_post", return_value={"jobId": "s1"}), \
         patch.object(M, "_http_get", return_value={"status": "done", "tileMeshUri": "ipfs://glb", "triangleCount": 4800}), \
         patch.object(M.time, "sleep", lambda *_: None):
        out = _run(M.task_maps3d_simplify_and_export(tileH3="t", rawMeshUri="ipfs://m"))
    assert out["ok"] is True
    assert out["tileMeshUri"] == "ipfs://glb"
    assert out["triangleCount"] == 4800


def test_simplify_poll_failed():
    with patch.object(M, "_http_post", return_value={"jobId": "s1"}), \
         patch.object(M, "_http_get", return_value={"status": "failed", "errorMessage": "non-manifold"}), \
         patch.object(M.time, "sleep", lambda *_: None):
        out = _run(M.task_maps3d_simplify_and_export(tileH3="t", rawMeshUri="ipfs://m"))
    assert out["ok"] is False
    assert "non-manifold" in out["error"]


# ─── visionAnnotate: parse LLM JSON, dedup, confidence filter ─────────────────

def test_vision_parses_and_filters():
    content = ('noise {"detections":[{"label":"Starbucks","confidence":0.9,"category":"business"},'
               '{"label":"Blur","confidence":0.2}]} trailing')
    with patch.object(M._llm, "call_tier", return_value={"content": content}), \
         patch.object(M, "get_kotoba_client", return_value=_FakeClient()):
        out = _run(M.task_maps3d_vision_annotate(tileH3="t",
                                                 imageRefs=[{"id": "i1", "thumbUrl": "http://x/1"}],
                                                 minConfidence=0.55))
    assert len(out["detections"]) == 1               # low-confidence dropped
    assert out["detections"][0]["label"] == "Starbucks"


def test_vision_dedupes_labels_across_images():
    with patch.object(M._llm, "call_tier", return_value={"content": '{"detections":[{"label":"Tower","confidence":0.9}]}'}), \
         patch.object(M, "get_kotoba_client", return_value=_FakeClient()):
        out = _run(M.task_maps3d_vision_annotate(tileH3="t",
                                                 imageRefs=[{"id": "i1", "thumbUrl": "u1"},
                                                            {"id": "i2", "thumbUrl": "u2"}]))
    assert len(out["detections"]) == 1               # same label deduped


def test_vision_persists_detections():
    fake = _FakeClient()
    with patch.object(M._llm, "call_tier", return_value={"content": '{"detections":[{"label":"Cafe","confidence":0.9}]}'}), \
         patch.object(M, "get_kotoba_client", return_value=fake):
        out = _run(M.task_maps3d_vision_annotate(tileH3="t", imageRefs=[{"id": "i1", "thumbUrl": "u1"}]))
    assert out["persisted"] == 1
    assert fake.inserts and fake.inserts[0][0] == "vertex_vision_result"


# ─── linkActor: parse links, confidence filter, persist ──────────────────────

def test_link_parses_and_filters_and_persists():
    fake = _FakeClient()
    llm_ret = {"ok": True, "data": {"links": [
        {"label": "Starbucks", "actorDid": "did:web:a", "confidence": 0.95},
        {"label": "Weak", "actorDid": "did:web:b", "confidence": 0.4},   # below min
        {"label": "NoDid", "actorDid": "", "confidence": 0.99},          # no DID
    ]}}
    with patch.object(M, "get_kotoba_client", return_value=fake), \
         patch.object(M._llm, "call_tier_json", return_value=llm_ret):
        out = _run(M.task_maps3d_link_actor(tileH3="t", detections=[{"label": "Starbucks"}], minConfidence=0.7))
    assert len(out["links"]) == 1
    assert out["links"][0]["actorDid"] == "did:web:a"
    assert out["persisted"] == 1
    assert fake.inserts[0][0] == "edge_maps3d_actor_link"


class _FakeClient:
    """Records insert_row upserts; serves empty registry for select_where."""

    def __init__(self):
        self.inserts = []

    def insert_row(self, table, row):
        self.inserts.append((table, dict(row)))
        return {"datom_count": len(row)}

    def select_where(self, *_a, **_k):
        return []
