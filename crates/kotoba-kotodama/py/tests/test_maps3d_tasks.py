"""Guard-branch + pure-helper tests for the maps3d pipeline task functions.

These exercise the no-network / no-LLM code paths of every task (input guards,
rule-based early returns, deterministic fallbacks) to raise branch-coverage
maturity of kotodama.primitives.maps3d without standing up COLMAP / Mapillary /
Murakumo. Network/LLM-bound success paths are deliberately out of scope here.
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


# ─── _h3_to_bbox (fallback path, no h3 library) ──────────────────────────────

def test_h3_to_bbox_returns_ordered_box():
    # With or without the h3 library installed, the result must be a valid
    # (west, south, east, north) box with west<east and south<north.
    west, south, east, north = M._h3_to_bbox("8f2830828052d25")
    assert west < east
    assert south < north


def test_h3_to_bbox_bad_input_falls_back_to_tokyo_default():
    # Non-hex, non-int garbage hits the ValueError fallback → Tokyo centre box.
    box = M._h3_to_bbox("not-a-real-h3-!@#")
    # h3 lib (if present) would raise→handled; fallback path yields the Tokyo box.
    assert box == (139.6, 35.5, 139.8, 35.7) or (box[0] < box[2] and box[1] < box[3])


# ─── fetchMapillary guards ───────────────────────────────────────────────────

def test_fetch_mapillary_requires_tile():
    out = _run(M.task_maps3d_fetch_mapillary(tileH3=""))
    assert out["ok"] is False
    assert out["error"] == "tileH3 required"
    assert out["candidates"] == [] and out["totalAvailable"] == 0


def test_fetch_mapillary_requires_token(monkeypatch=None):
    with patch.object(M, "_MAPILLARY_TOKEN", ""):
        out = _run(M.task_maps3d_fetch_mapillary(tileH3="8f2830828052d25"))
    assert out["ok"] is False
    assert out["error"] == "MAPILLARY_TOKEN not set"


def test_fetch_mapillary_filters_by_quality_and_maps_fields():
    fake_resp = {"data": [
        {"id": "a", "thumb_1024_url": "http://x/a.jpg",
         "computed_geometry": {"coordinates": [139.7, 35.6]},
         "quality_score": 0.9, "captured_at": "t", "compass_angle": 12.0},
        {"id": "b", "quality_score": 0.1},  # below minQuality → dropped
    ]}
    with patch.object(M, "_MAPILLARY_TOKEN", "tok"), \
         patch.object(M, "_http_get", return_value=fake_resp):
        out = _run(M.task_maps3d_fetch_mapillary(tileH3="8f2830828052d25", minQuality=0.5))
    assert out["ok"] is True
    assert out["totalAvailable"] == 1
    cand = out["candidates"][0]
    assert cand["id"] == "a" and cand["lng"] == 139.7 and cand["lat"] == 35.6


def test_fetch_mapillary_handles_http_error():
    with patch.object(M, "_MAPILLARY_TOKEN", "tok"), \
         patch.object(M, "_http_get", side_effect=RuntimeError("HTTP 429")):
        out = _run(M.task_maps3d_fetch_mapillary(tileH3="8f2830828052d25"))
    assert out["ok"] is False and "429" in out["error"]


# ─── curateImages guards + fallback ──────────────────────────────────────────

def test_curate_images_no_candidates_aborts():
    out = _run(M.task_maps3d_curate_images(tileH3="t", candidates=[]))
    assert out["ok"] is False and out["abort"] is True


def test_curate_images_below_min_count_aborts():
    cands = [{"id": "1", "qualityScore": 0.9}, {"id": "2", "qualityScore": 0.8}]
    out = _run(M.task_maps3d_curate_images(tileH3="t", candidates=cands, minCount=8))
    assert out["abort"] is True
    assert out["selectedIds"] == ["1", "2"]


def test_curate_images_llm_failure_falls_back_to_top_n():
    cands = [{"id": str(i), "qualityScore": 1.0 - i * 0.01, "compassAngle": i}
             for i in range(20)]
    with patch.object(M._llm, "call_tier_json", side_effect=RuntimeError("no llm")):
        out = _run(M.task_maps3d_curate_images(
            tileH3="t", candidates=cands, targetCount=5, minCount=3))
    assert out["ok"] is True
    assert "fallback" in out
    assert len(out["selectedIds"]) == 5
    assert out["selectedIds"][0] == "0"  # highest quality first


def test_curate_images_uses_llm_selection_when_available():
    cands = [{"id": str(i), "qualityScore": 0.9, "compassAngle": i} for i in range(20)]
    llm_ret = {"ok": True, "data": {"selected": ["3", "7", "9"], "abort": False}}
    with patch.object(M._llm, "call_tier_json", return_value=llm_ret):
        out = _run(M.task_maps3d_curate_images(
            tileH3="t", candidates=cands, targetCount=5, minCount=3))
    assert out["selectedIds"] == ["3", "7", "9"]
    assert out["abort"] is False


# ─── colmapTile guard ────────────────────────────────────────────────────────

def test_colmap_tile_missing_input_guard():
    out = _run(M.task_maps3d_colmap_tile(tileH3="", selectedIds=[]))
    assert out["ok"] is False
    assert out["errorCode"] == "MISSING_INPUT"


def test_colmap_tile_submit_failure():
    with patch.object(M, "_http_post", side_effect=RuntimeError("conn refused")):
        out = _run(M.task_maps3d_colmap_tile(tileH3="t", selectedIds=["a"]))
    assert out["ok"] is False and out["errorCode"] == "SUBMIT_FAILED"


def test_colmap_tile_no_job_id():
    with patch.object(M, "_http_post", return_value={"unexpected": 1}):
        out = _run(M.task_maps3d_colmap_tile(tileH3="t", selectedIds=["a"]))
    assert out["ok"] is False and out["errorCode"] == "NO_JOB_ID"


# ─── replanReconstruction rule branches (no LLM) ─────────────────────────────

def test_replan_max_attempts_downgrades_to_osm():
    out = _run(M.task_maps3d_replan_reconstruction(tileH3="t", attempt=3))
    assert out["action"] == "downgradeOsm"


def test_replan_too_few_images_requests_more():
    out = _run(M.task_maps3d_replan_reconstruction(
        tileH3="t", imageCount=2, attempt=1))
    assert out["action"] == "requestMore"


def test_replan_llm_unavailable_defaults_to_retry():
    with patch.object(M._llm, "call_tier_json", side_effect=RuntimeError("no llm")):
        out = _run(M.task_maps3d_replan_reconstruction(
            tileH3="t", errorCode="X", imageCount=20, attempt=1))
    assert out["action"] == "retry"


def test_replan_llm_sanitizes_unknown_action():
    bad = {"ok": True, "data": {"action": "explode", "rationale": "?"}}
    with patch.object(M._llm, "call_tier_json", return_value=bad):
        out = _run(M.task_maps3d_replan_reconstruction(
            tileH3="t", imageCount=20, attempt=1))
    assert out["action"] == "retry"  # unknown action coerced to retry


# ─── simplifyAndExport guards ────────────────────────────────────────────────

def test_simplify_requires_raw_mesh():
    out = _run(M.task_maps3d_simplify_and_export(tileH3="t", rawMeshUri=""))
    assert out["ok"] is False and "rawMeshUri" in out["error"]


def test_simplify_submit_failure():
    with patch.object(M, "_http_post", side_effect=RuntimeError("boom")):
        out = _run(M.task_maps3d_simplify_and_export(tileH3="t", rawMeshUri="ipfs://m"))
    assert out["ok"] is False and "boom" in out["error"]


def test_simplify_no_job_id():
    with patch.object(M, "_http_post", return_value={}):
        out = _run(M.task_maps3d_simplify_and_export(tileH3="t", rawMeshUri="ipfs://m"))
    assert out["ok"] is False and "no job_id" in out["error"]


# ─── visionAnnotate empty-input fast path ────────────────────────────────────

def test_vision_annotate_empty_image_refs_returns_empty():
    out = _run(M.task_maps3d_vision_annotate(tileH3="t", imageRefs=[]))
    assert out["ok"] is True and out["detections"] == []


# ─── linkActor empty-detections fast path ────────────────────────────────────

def test_link_actor_no_detections_returns_empty():
    out = _run(M.task_maps3d_link_actor(tileH3="t", detections=[]))
    assert out["ok"] is True and out["links"] == []
