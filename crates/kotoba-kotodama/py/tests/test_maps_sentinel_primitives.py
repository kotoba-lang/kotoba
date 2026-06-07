"""Unit tests for maps_sentinel Zeebe primitives."""

from __future__ import annotations

import json
import sys
import time
import urllib.error as _u_err
from io import BytesIO
from pathlib import Path as _P
from typing import Any
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import maps_sentinel as MS  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self):
        self.sqls: list[str] = []
        self.params: list[Any] = []

    def execute(self, sql: str, params: Any = None) -> None:
        self.sqls.append(sql)
        self.params.append(params)


class _FakeCursorCtx:
    def __init__(self):
        self.cursor = _FakeCursor()

    def __enter__(self) -> _FakeCursor:
        return self.cursor

    def __exit__(self, *_: Any) -> bool:
        return False


def _fake_urlopen(resp_body: bytes, *, status: int = 200):
    """Return a context-manager mock that yields a response-like object."""

    class _Resp:
        def read(self) -> bytes:
            return resp_body

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    return _Resp()


def _stac_feature(feat_id: str = "S2A_1234", platform: str = "sentinel-2-l2a") -> dict[str, Any]:
    return {
        "id": feat_id,
        "type": "Feature",
        "bbox": [139.7, 35.4, 140.0, 35.7],
        "geometry": {"type": "Polygon", "coordinates": [[]]},
        "properties": {
            "datetime": "2026-04-20T03:00:00Z",
            "eo:cloud_cover": 5.2,
            "platform": platform,
            "collection": "sentinel-2-l2a",
        },
        "links": [{"rel": "self", "href": "https://stac.example.com/items/S2A_1234"}],
    }


# ── _parse_aoi ────────────────────────────────────────────────────────────────

def test_parse_aoi_valid():
    raw = {"name": "tokyo_bay", "bbox": [139.7, 35.4, 140.0, 35.7]}
    result = MS._parse_aoi(raw)
    assert result["name"] == "tokyo_bay"
    assert result["bbox"] == [139.7, 35.4, 140.0, 35.7]


def test_parse_aoi_coerces_strings_to_float():
    raw = {"name": "test", "bbox": ["130.0", "33.0", "131.0", "34.0"]}
    result = MS._parse_aoi(raw)
    assert result["bbox"] == [130.0, 33.0, 131.0, 34.0]


def test_parse_aoi_rejects_non_dict():
    try:
        MS._parse_aoi([1, 2, 3, 4])
        assert False, "Should have raised"
    except ValueError as exc:
        assert "dict" in str(exc)


def test_parse_aoi_rejects_wrong_bbox_length():
    try:
        MS._parse_aoi({"name": "x", "bbox": [1.0, 2.0]})
        assert False, "Should have raised"
    except ValueError as exc:
        assert "bbox" in str(exc)


def test_parse_aoi_rejects_inverted_longitude():
    try:
        MS._parse_aoi({"name": "x", "bbox": [140.0, 35.0, 139.0, 36.0]})  # west > east
        assert False, "Should have raised"
    except ValueError as exc:
        assert "longitude" in str(exc)


def test_parse_aoi_rejects_inverted_latitude():
    try:
        MS._parse_aoi({"name": "x", "bbox": [139.0, 36.0, 140.0, 35.0]})  # south > north
        assert False, "Should have raised"
    except ValueError as exc:
        assert "latitude" in str(exc)


# ── _resolve_aois ─────────────────────────────────────────────────────────────

def test_resolve_aois_returns_bootstrap_by_default(monkeypatch):
    monkeypatch.delenv("SENTINEL_AOIS_JSON", raising=False)
    aois = MS._resolve_aois()
    assert len(aois) == 12
    assert aois[0]["name"] == "tokyo_bay"


def test_resolve_aois_uses_override():
    override = [{"name": "custom", "bbox": [130.0, 33.0, 131.0, 34.0]}]
    aois = MS._resolve_aois(override)
    assert len(aois) == 1
    assert aois[0]["name"] == "custom"


def test_resolve_aois_uses_env(monkeypatch):
    env_val = json.dumps([{"name": "env_aoi", "bbox": [135.0, 34.0, 136.0, 35.0]}])
    monkeypatch.setenv("SENTINEL_AOIS_JSON", env_val)
    aois = MS._resolve_aois()
    assert len(aois) == 1
    assert aois[0]["name"] == "env_aoi"


def test_resolve_aois_override_takes_priority_over_env(monkeypatch):
    monkeypatch.setenv("SENTINEL_AOIS_JSON", json.dumps([{"name": "env", "bbox": [1, 2, 3, 4]}]))
    override = [{"name": "override", "bbox": [130.0, 33.0, 131.0, 34.0]}]
    aois = MS._resolve_aois(override)
    assert aois[0]["name"] == "override"


# ── _scene_row_from_stac ──────────────────────────────────────────────────────

def test_scene_row_from_stac_shape():
    feature = _stac_feature("S2A_TEST_001")
    row = MS._scene_row_from_stac(feature, platform="sentinel-2-l2a")

    assert row["collection"] == "com.etzhayyim.apps.maps.satelliteScene"
    assert row["repo"] == MS.DEFAULT_REPO
    assert row["uri"].startswith(f"at://{MS.DEFAULT_REPO}/com.etzhayyim.apps.maps.satelliteScene/")
    assert row["rkey"] == row["cid"]
    assert row["vertex_id"] == row["uri"]
    assert isinstance(row["ts_ms"], int)

    record = json.loads(row["value_json"])
    assert record["$type"] == "com.etzhayyim.apps.maps.satelliteScene"
    assert record["sceneId"] == "S2A_TEST_001"
    assert record["platform"] == "sentinel-2-l2a"
    assert record["cloudCover"] == 5.2
    assert record["stacSelfUrl"] == "https://stac.example.com/items/S2A_1234"


def test_scene_row_from_stac_rkey_is_stable():
    feature = _stac_feature("fixed_id")
    row1 = MS._scene_row_from_stac(feature)
    row2 = MS._scene_row_from_stac(feature)
    assert row1["rkey"] == row2["rkey"]


def test_scene_row_from_stac_rkey_differs_by_feature_id():
    row1 = MS._scene_row_from_stac(_stac_feature("id_A"))
    row2 = MS._scene_row_from_stac(_stac_feature("id_B"))
    assert row1["rkey"] != row2["rkey"]


def test_scene_row_uses_fallback_platform():
    feature = _stac_feature("S2A_XYZ")
    feature["properties"].pop("platform", None)
    feature["properties"]["constellation"] = "sentinel-2"
    row = MS._scene_row_from_stac(feature, platform="")
    record = json.loads(row["value_json"])
    assert record["platform"] == "sentinel-2"


# ── _stac_search ─────────────────────────────────────────────────────────────

def test_stac_search_returns_features_on_success():
    features_payload = json.dumps({"features": [_stac_feature()]}).encode()

    with patch("urllib.request.urlopen", return_value=_fake_urlopen(features_payload)):
        result = MS._stac_search(
            MS.ELEMENT84_STAC, "sentinel-2-l2a", [139.7, 35.4, 140.0, 35.7]
        )

    assert len(result) == 1
    assert result[0]["id"] == "S2A_1234"


def test_stac_search_returns_empty_on_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        result = MS._stac_search(
            MS.ELEMENT84_STAC, "sentinel-2-l2a", [139.7, 35.4, 140.0, 35.7]
        )
    assert result == []


def test_stac_search_returns_empty_on_http_error():
    err = _u_err.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=None)  # type: ignore
    with patch("urllib.request.urlopen", side_effect=err):
        result = MS._stac_search(MS.COPERNICUS_STAC, "sentinel-1-grd", [0, 0, 1, 1])
    assert result == []


def test_stac_search_sends_cloud_cover_filter():
    """Verify the cloud cover query is only added when < 100."""
    captured_reqs: list[Any] = []

    def _capture(req, timeout=None):
        captured_reqs.append(req)
        return _fake_urlopen(b'{"features":[]}')

    with patch("urllib.request.urlopen", side_effect=_capture):
        MS._stac_search(
            MS.ELEMENT84_STAC, "sentinel-2-l2a", [0, 0, 1, 1], max_cloud_cover=25.0
        )

    assert len(captured_reqs) == 1
    body = json.loads(captured_reqs[0].data.decode())
    assert body["query"]["eo:cloud_cover"]["lte"] == 25.0


# ── _runpod_invoke_sync ───────────────────────────────────────────────────────

def test_runpod_invoke_sync_returns_degraded_without_credentials():
    result = MS._runpod_invoke_sync(
        "change_detection", "at://test/scene/001", api_key="", endpoint_id=""
    )
    assert result["ok"] is False
    assert "not configured" in result["reason"]
    assert result["confidence"] == 0.0


def test_runpod_invoke_sync_completed_path():
    run_resp = json.dumps({"id": "job-abc-123"}).encode()
    status_resp = json.dumps({
        "status": "COMPLETED",
        "output": {"summary": "Change detected", "confidence": 0.82},
    }).encode()

    call_count = 0

    def _mock_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fake_urlopen(run_resp)
        return _fake_urlopen(status_resp)

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen), \
         patch("time.sleep"):
        result = MS._runpod_invoke_sync(
            "change_detection",
            "at://maps.etzhayyim.com/scene/001",
            api_key="rp_test_key",
            endpoint_id="ep123",
        )

    assert result["ok"] is True
    assert result["summary"] == "Change detected"
    assert result["confidence"] == 0.82
    assert result["analysisType"] == "change_detection"


def test_runpod_invoke_sync_failed_status_raises():
    run_resp = json.dumps({"id": "job-fail"}).encode()
    status_resp = json.dumps({"status": "FAILED", "error": "OOM"}).encode()

    call_count = 0

    def _mock_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fake_urlopen(run_resp)
        return _fake_urlopen(status_resp)

    try:
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen), \
             patch("time.sleep"):
            MS._runpod_invoke_sync(
                "land_use",
                "at://maps.etzhayyim.com/scene/002",
                api_key="key",
                endpoint_id="ep",
            )
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "FAILED" in str(exc)
        assert "OOM" in str(exc)


def test_runpod_invoke_sync_timeout_raises():
    run_resp = json.dumps({"id": "job-slow"}).encode()
    in_progress = json.dumps({"status": "IN_PROGRESS"}).encode()

    original_max_polls = MS._RUNPOD_MAX_POLLS
    MS._RUNPOD_MAX_POLLS = 2

    call_count = 0

    def _mock_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fake_urlopen(run_resp)
        return _fake_urlopen(in_progress)

    try:
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen), \
             patch("time.sleep"):
            MS._runpod_invoke_sync(
                "sar_flood", "at://test/s/1", api_key="k", endpoint_id="e"
            )
        assert False, "Expected TimeoutError"
    except TimeoutError as exc:
        assert "job-slow" in str(exc)
    finally:
        MS._RUNPOD_MAX_POLLS = original_max_polls


# ── LangChain stage functions ─────────────────────────────────────────────────

def test_stage1_normalises_unknown_analysis_type():
    inputs = {
        "scene_uri": "at://x/y/z",
        "analysis_type": "not_valid",
        "api_key": "k",
        "endpoint_id": "e",
    }
    out = MS._stage1_build_input(inputs)
    assert out["analysis_type"] == "change_detection"


def test_stage1_passes_through_valid_types():
    for t in ("change_detection", "land_use", "sar_flood"):
        inputs = {"scene_uri": "at://x", "analysis_type": t, "api_key": "", "endpoint_id": ""}
        out = MS._stage1_build_input(inputs)
        assert out["analysis_type"] == t


def test_stage3_clamps_confidence_above_1():
    out = MS._stage3_parse_output({"confidence": 1.5, "model_version": "v2"})
    assert out["confidence"] == 1.0


def test_stage3_clamps_confidence_below_0():
    out = MS._stage3_parse_output({"confidence": -0.1, "model_version": "v2"})
    assert out["confidence"] == 0.0


def test_stage3_caps_phase1_at_085():
    out = MS._stage3_parse_output({"confidence": 0.99, "model_version": "phase1"})
    assert out["confidence"] == 0.85


def test_stage3_does_not_cap_non_phase1():
    out = MS._stage3_parse_output({"confidence": 0.95, "model_version": "v2"})
    assert out["confidence"] == 0.95


def test_stage3_adds_default_fields():
    out = MS._stage3_parse_output({})
    assert "summary" in out
    assert out["ok"] is True


# ── task_maps_sentinel_stac_search ────────────────────────────────────────────

def test_task_stac_search_writes_rows_to_db(monkeypatch):
    monkeypatch.delenv("SENTINEL_AOIS_JSON", raising=False)

    feature = _stac_feature("SCENE_001")
    stac_payload = json.dumps({"features": [feature]}).encode()

    ctx = _FakeCursorCtx()

    with patch("urllib.request.urlopen", return_value=_fake_urlopen(stac_payload)), \
         patch("kotodama.primitives.maps_sentinel.sync_cursor", return_value=ctx):
        result = MS.task_maps_sentinel_stac_search(
            aois=[{"name": "test", "bbox": [139.7, 35.4, 140.0, 35.7]}],
            platforms=["sentinel-2-l2a"],
            max_scenes_per_aoi=5,
        )

    assert result["scenesFound"] == 1
    assert result["scenesIngested"] == 1
    assert len(ctx.cursor.sqls) == 1
    assert "INSERT INTO vertex_satellite_scene" in ctx.cursor.sqls[0]
    assert "WHERE NOT EXISTS" in ctx.cursor.sqls[0]


def test_task_stac_search_skips_s1_without_token(monkeypatch):
    monkeypatch.delenv("COPERNICUS_OAUTH_TOKEN", raising=False)
    call_count = 0

    def _mock_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        return _fake_urlopen(b'{"features":[]}')

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen):
        MS.task_maps_sentinel_stac_search(
            aois=[{"name": "test", "bbox": [139.7, 35.4, 140.0, 35.7]}],
            platforms=["sentinel-1-grd", "sentinel-2-l2a"],
        )

    # Both platform requests go through (S1 gracefully returns [])
    assert call_count == 2


def test_task_stac_search_no_results_skips_db_write(monkeypatch):
    monkeypatch.delenv("SENTINEL_AOIS_JSON", raising=False)

    with patch("urllib.request.urlopen", return_value=_fake_urlopen(b'{"features":[]}')), \
         patch("kotodama.primitives.maps_sentinel.sync_cursor") as mock_cursor:
        result = MS.task_maps_sentinel_stac_search(
            aois=[{"name": "t", "bbox": [130.0, 33.0, 131.0, 34.0]}],
            platforms=["sentinel-2-l2a"],
        )

    assert result["scenesFound"] == 0
    assert result["scenesIngested"] == 0
    mock_cursor.assert_not_called()


# ── task_maps_sentinel_runpod_analyze ─────────────────────────────────────────

def test_task_runpod_analyze_without_credentials_writes_degraded_row(monkeypatch):
    monkeypatch.delenv("RUNPOD_KEY", raising=False)
    monkeypatch.delenv("RUNPOD_ENDPOINT_ID_MAPS", raising=False)

    ctx = _FakeCursorCtx()

    with patch("kotodama.primitives.maps_sentinel.sync_cursor", return_value=ctx):
        result = MS.task_maps_sentinel_runpod_analyze(
            scene_uri="at://maps.etzhayyim.com/com.etzhayyim.apps.maps.satelliteScene/abc123",
            analysis_type="change_detection",
        )

    assert result["ok"] is False
    assert result["analysisUri"].startswith("at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.satelliteAnalysis/")
    assert len(ctx.cursor.sqls) == 1

    record = json.loads(ctx.cursor.params[0][5])  # value_json is index 5
    assert record["$type"] == "com.etzhayyim.apps.maps.satelliteAnalysis"
    assert record["analysisType"] == "change_detection"
    assert record["confidence"] == 0.0


def test_task_runpod_analyze_with_credentials_writes_result(monkeypatch):
    monkeypatch.setenv("RUNPOD_KEY", "rp_test")
    monkeypatch.setenv("RUNPOD_ENDPOINT_ID_MAPS", "ep_maps_01")

    run_resp = json.dumps({"id": "job-ok"}).encode()
    status_resp = json.dumps({
        "status": "COMPLETED",
        "output": {"summary": "Flood detected in low-lying area", "confidence": 0.79},
    }).encode()

    call_count = 0

    def _mock_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fake_urlopen(run_resp)
        return _fake_urlopen(status_resp)

    ctx = _FakeCursorCtx()

    with patch("urllib.request.urlopen", side_effect=_mock_urlopen), \
         patch("time.sleep"), \
         patch("kotodama.primitives.maps_sentinel.sync_cursor", return_value=ctx):
        result = MS.task_maps_sentinel_runpod_analyze(
            scene_uri="at://maps.etzhayyim.com/com.etzhayyim.apps.maps.satelliteScene/s1flood",
            analysis_type="sar_flood",
            model_version="phase1",
        )

    assert result["ok"] is True
    assert result["summary"] == "Flood detected in low-lying area"
    # phase1 cap: 0.79 < 0.85 → unchanged
    assert result["confidence"] == 0.79
    assert result["analysisUri"].startswith("at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.satelliteAnalysis/")

    record = json.loads(ctx.cursor.params[0][5])
    assert record["sceneUri"] == "at://maps.etzhayyim.com/com.etzhayyim.apps.maps.satelliteScene/s1flood"
    assert record["analysisType"] == "sar_flood"
    assert record["modelVersion"] == "phase1"


# ── register ──────────────────────────────────────────────────────────────────

def test_register_exposes_two_pyzeebe_tasks():
    registered: list[tuple[str, bool, int]] = []

    class _FakeWorker:
        def task(self, *, task_type: str, single_value: bool, timeout_ms: int):
            registered.append((task_type, single_value, timeout_ms))

            def decorator(fn):
                return fn

            return decorator

    MS.register(_FakeWorker(), timeout_ms=180_000)

    task_types = [r[0] for r in registered]
    assert "maps.sentinel.stac.search" in task_types
    assert "maps.sentinel.runpod.analyze" in task_types

    for task_type, single_value, timeout_ms in registered:
        assert single_value is False
        if task_type == "maps.sentinel.stac.search":
            assert timeout_ms == 180_000
        elif task_type == "maps.sentinel.runpod.analyze":
            # analyze timeout must be at least 600s
            assert timeout_ms >= 600_000


def test_register_analyze_timeout_uses_max_of_arg_and_600s():
    registered: list[tuple[str, bool, int]] = []

    class _FakeWorker:
        def task(self, *, task_type: str, single_value: bool, timeout_ms: int):
            registered.append((task_type, single_value, timeout_ms))

            def decorator(fn):
                return fn

            return decorator

    MS.register(_FakeWorker(), timeout_ms=1_000_000)

    analyze_entry = next(r for r in registered if r[0] == "maps.sentinel.runpod.analyze")
    assert analyze_entry[2] == 1_000_000  # max(1_000_000, 600_000) = 1_000_000
