"""Pure-helper tests for aismarine primitives (ADR-2605011500).

Covers pure functions with no DB / HTTP dependencies:
- _haversine_km / _vessel_vid / _position_vid / _voyage_vid / _visited_edge_id
- _coerce_int / _coerce_float
- task_aismarine_query_bbox guard branches (no DB call)
- task_aismarine_position_batch_insert validation branches (DB mocked)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import aismarine as A


# ─── haversine ────────────────────────────────────────────────────────────────

def test_haversine_zero_distance_self():
    assert A._haversine_km(35.45, 139.65, 35.45, 139.65) == pytest.approx(0.0, abs=1e-6)


def test_haversine_short_distance_yokohama():
    d = A._haversine_km(35.45, 139.65, 35.46, 139.66)
    assert 1.0 < d < 2.0


def test_haversine_one_degree_lat_is_roughly_111_km():
    d = A._haversine_km(35.0, 139.0, 36.0, 139.0)
    assert 110.0 < d < 112.0


def test_haversine_antimeridian_short():
    d = A._haversine_km(0.0, 179.5, 0.0, -179.5)
    # 1 deg longitude at equator ~111 km; 179.5 vs -179.5 is 1 deg apart over antimeridian
    assert 100.0 < d < 120.0


# ─── vid helpers ──────────────────────────────────────────────────────────────

def test_vessel_vid():
    assert A._vessel_vid(431999000) == "mmsi:431999000"


def test_position_vid():
    assert A._position_vid(431999000, 1714512000000) == "mmsi:431999000:ts:1714512000000"


def test_voyage_vid():
    assert A._voyage_vid(431999000, 1714512000000) == "mmsi:431999000:voy:1714512000000"


def test_visited_edge_id():
    assert (
        A._visited_edge_id(431999000, "JPYOK", 1714512000000)
        == "mmsi:431999000:port:JPYOK:arr:1714512000000"
    )


# ─── coerce ───────────────────────────────────────────────────────────────────

def test_coerce_int_valid():
    assert A._coerce_int(42) == 42
    assert A._coerce_int("42") == 42
    assert A._coerce_int(42.7) == 42


def test_coerce_int_none_empty_invalid():
    assert A._coerce_int(None) is None
    assert A._coerce_int("") is None
    assert A._coerce_int("not a number") is None


def test_coerce_float_valid():
    assert A._coerce_float(1.5) == 1.5
    assert A._coerce_float("1.5") == 1.5


def test_coerce_float_rejects_nan_inf():
    assert A._coerce_float(float("nan")) is None
    assert A._coerce_float(float("inf")) is None
    assert A._coerce_float(float("-inf")) is None


# ─── constants ────────────────────────────────────────────────────────────────

def test_arrival_nav_statuses_includes_moored_anchored_undef():
    assert 1 in A._ARRIVAL_NAV_STATUSES   # at_anchor
    assert 5 in A._ARRIVAL_NAV_STATUSES   # moored
    assert 15 in A._ARRIVAL_NAV_STATUSES  # undefined / fallback


def test_voyage_port_radius_is_positive():
    assert A._VOYAGE_PORT_RADIUS_KM > 0


def test_default_repo_is_maps_did_web():
    assert A.DEFAULT_REPO == "did:web:maps.etzhayyim.com"


def test_source_constant():
    assert A.SOURCE_AISSTREAM == "aisstream"


# ─── query_bbox guard branches (no DB call) ───────────────────────────────────

def test_query_bbox_none_returns_empty():
    out = A.task_aismarine_query_bbox(bbox=None)
    assert out["features"] == []
    assert out["total"] == 0
    assert out["truncated"] is False


def test_query_bbox_wrong_shape_returns_empty():
    out = A.task_aismarine_query_bbox(bbox=[1, 2])
    assert out["features"] == []
    assert out["total"] == 0


def test_query_bbox_non_numeric_returns_empty():
    out = A.task_aismarine_query_bbox(bbox=["a", "b", "c", "d"])
    assert out["features"] == []
    assert out["total"] == 0


# ─── batch insert validation (DB mocked) ──────────────────────────────────────

def test_batch_insert_empty_skips_db():
    out = A.task_aismarine_position_batch_insert(positions=[])
    assert out == {"ok": True, "rows_inserted": 0, "rows_dropped": 0}


def test_batch_insert_none_skips_db():
    out = A.task_aismarine_position_batch_insert(positions=None)
    assert out == {"ok": True, "rows_inserted": 0, "rows_dropped": 0}


def test_batch_insert_drops_missing_required_fields():
    with patch("kotodama.primitives.aismarine.sync_cursor"):
        out = A.task_aismarine_position_batch_insert(
            positions=[{"mmsi": None, "ts_ms": 1, "lat": 35.0, "lon": 139.0}]
        )
        assert out["rows_dropped"] == 1
        assert out["rows_inserted"] == 0


def test_batch_insert_drops_out_of_range_lat():
    with patch("kotodama.primitives.aismarine.sync_cursor"):
        out = A.task_aismarine_position_batch_insert(
            positions=[{"mmsi": 431999000, "ts_ms": 1, "lat": 91.0, "lon": 0.0}]
        )
        assert out["rows_dropped"] == 1
        assert out["rows_inserted"] == 0


def test_batch_insert_drops_out_of_range_lon():
    with patch("kotodama.primitives.aismarine.sync_cursor"):
        out = A.task_aismarine_position_batch_insert(
            positions=[{"mmsi": 431999000, "ts_ms": 1, "lat": 35.0, "lon": 181.0}]
        )
        assert out["rows_dropped"] == 1
        assert out["rows_inserted"] == 0


def test_batch_insert_non_dict_dropped():
    with patch("kotodama.primitives.aismarine.sync_cursor"):
        out = A.task_aismarine_position_batch_insert(positions=["garbage", 42, None])
        assert out["rows_dropped"] == 3
        assert out["rows_inserted"] == 0


# ─── master_refresh limit clamping (DB mocked) ────────────────────────────────

def test_master_refresh_clamps_limit_high():
    captured: list[str] = []

    class _Cur:
        def execute(self, sql, params=()):
            captured.append(sql)

        def fetchall(self):
            return []

    class _CM:
        def __enter__(self):
            return _Cur()

        def __exit__(self, *exc):
            return False

    with patch("kotodama.primitives.aismarine.sync_cursor", return_value=_CM()):
        out = A.task_aismarine_master_refresh(limit=999_999)
    assert out == {"ok": True, "rows_scanned": 0, "rows_updated": 0}
    # limit was clamped; SQL contains LIMIT 50000 (max cap)
    assert any("LIMIT 50000" in s for s in captured)


def test_master_refresh_clamps_limit_low():
    captured: list[str] = []

    class _Cur:
        def execute(self, sql, params=()):
            captured.append(sql)

        def fetchall(self):
            return []

    class _CM:
        def __enter__(self):
            return _Cur()

        def __exit__(self, *exc):
            return False

    with patch("kotodama.primitives.aismarine.sync_cursor", return_value=_CM()):
        out = A.task_aismarine_master_refresh(limit=0)
    assert out == {"ok": True, "rows_scanned": 0, "rows_updated": 0}
    # limit=0 → defaulted to 5000
    assert any("LIMIT 5000" in s for s in captured)


# ─── voyage_detect_window early return ────────────────────────────────────────

def test_voyage_detect_window_no_positions():
    class _Cur:
        def execute(self, sql, params=()):
            pass

        def fetchall(self):
            return []

    class _CM:
        def __enter__(self):
            return _Cur()

        def __exit__(self, *exc):
            return False

    with patch("kotodama.primitives.aismarine.sync_cursor", return_value=_CM()):
        out = A.task_aismarine_voyage_detect_window(window_minutes=5)
    assert out == {"ok": True, "scanned": 0, "arrivals_recorded": 0, "voyages_opened": 0}


# ─── register wires 6 task types ──────────────────────────────────────────────

def test_register_six_task_types():
    registered: list[str] = []

    class _Worker:
        def task(self, *, task_type, single_value, timeout_ms):
            def _decorator(fn):
                registered.append(task_type)
                return fn

            return _decorator

    A.register(_Worker(), timeout_ms=60_000)
    assert sorted(registered) == sorted([
        "aismarine.position.batchInsert",
        "aismarine.master.upsert",
        "aismarine.voyage.detectWindow",
        "aismarine.master.refresh",
        "aismarine.density.verify",
        "aismarine.query.bbox",
    ])
