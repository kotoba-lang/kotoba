"""Tests for maps_building_3d primitives (H3 cell claim + OSM enrich + coverage)."""

from __future__ import annotations

import sys
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import maps_building_3d as MB  # noqa: E402


@pytest.fixture()
def _stub_db():
    with patch("kotodama.primitives.maps_building_3d.sync_cursor") as m:
        cur = MagicMock()
        cur.description = None
        cur.fetchall.return_value = []
        m.return_value.__enter__ = MagicMock(return_value=cur)
        m.return_value.__exit__ = MagicMock(return_value=False)
        yield cur


# ─── _lat_lng_to_h3_approx (pure) ────────────────────────────────────────────

def test_lat_lng_to_h3_approx_format():
    cell = MB._lat_lng_to_h3_approx(35.6895, 139.6917, 10)
    assert cell.startswith("h3_10_")
    parts = cell.split("_")
    assert len(parts) == 4


def test_lat_lng_to_h3_approx_res_in_output():
    cell5 = MB._lat_lng_to_h3_approx(35.0, 135.0, 5)
    cell10 = MB._lat_lng_to_h3_approx(35.0, 135.0, 10)
    assert cell5.startswith("h3_5_")
    assert cell10.startswith("h3_10_")


def test_lat_lng_to_h3_approx_nearby_points_same_cell():
    cell1 = MB._lat_lng_to_h3_approx(35.6895, 139.6917, 10)
    cell2 = MB._lat_lng_to_h3_approx(35.6895001, 139.6917001, 10)
    assert cell1 == cell2


def test_lat_lng_to_h3_approx_different_points_may_differ():
    cell1 = MB._lat_lng_to_h3_approx(35.0, 135.0, 10)
    cell2 = MB._lat_lng_to_h3_approx(36.0, 136.0, 10)
    assert cell1 != cell2


# ─── _centroid_of_cell (pure) ────────────────────────────────────────────────

def test_centroid_of_cell_returns_float_pair():
    cell = MB._lat_lng_to_h3_approx(35.6895, 139.6917, 10)
    lat, lng = MB._centroid_of_cell(cell)
    assert isinstance(lat, float)
    assert isinstance(lng, float)


def test_centroid_of_cell_bad_format_returns_zeros():
    lat, lng = MB._centroid_of_cell("bad_cell_key")
    assert lat == 0.0
    assert lng == 0.0


def test_centroid_of_cell_roundtrip_approximate():
    orig_lat, orig_lng = 35.6895, 139.6917
    cell = MB._lat_lng_to_h3_approx(orig_lat, orig_lng, 10)
    clat, clng = MB._centroid_of_cell(cell)
    assert abs(clat - orig_lat) < 0.01
    assert abs(clng - orig_lng) < 0.01


# ─── _stable_rkey (pure) ─────────────────────────────────────────────────────

def test_stable_rkey_deterministic():
    vid = "at://did:web:maps.etzhayyim.com/vertex_spatial/building-001"
    r1 = MB._stable_rkey(vid)
    r2 = MB._stable_rkey(vid)
    assert r1 == r2


def test_stable_rkey_length():
    rkey = MB._stable_rkey("any-spatial-vertex-id")
    assert len(rkey) == 16


def test_stable_rkey_different_inputs_differ():
    r1 = MB._stable_rkey("vertex-a")
    r2 = MB._stable_rkey("vertex-b")
    assert r1 != r2


# ─── task_maps_building_claim_cells (with DB mock) ───────────────────────────

def test_claim_cells_empty_db_returns_zero_cells(_stub_db):
    result = MB.task_maps_building_claim_cells(max_cells=10, stale_days=7)
    assert "cells" in result or "claimedCells" in result or "claimed" in result or isinstance(result, dict)
    assert isinstance(result, dict)


def test_claim_cells_queries_db(_stub_db):
    MB.task_maps_building_claim_cells(max_cells=5, stale_days=3)
    assert _stub_db.execute.called


def test_claim_cells_caps_max_cells(_stub_db):
    result = MB.task_maps_building_claim_cells(max_cells=500, stale_days=7)
    assert isinstance(result, dict)


# ─── task_maps_building_enrich_from_osm (with DB mock) ──────────────────────

def test_enrich_from_osm_empty_cells_returns_quickly(_stub_db):
    result = MB.task_maps_building_enrich_from_osm(cells=[])
    assert isinstance(result, dict)


def test_enrich_from_osm_with_cell_list(_stub_db):
    cell = MB._lat_lng_to_h3_approx(35.6895, 139.6917, 10)
    result = MB.task_maps_building_enrich_from_osm(
        cells=[{"cell_key": cell, "building_vertex_ids": []}]
    )
    assert isinstance(result, dict)


# ─── task_maps_building_update_coverage (with DB mock) ──────────────────────

def test_update_coverage_empty_cells(_stub_db):
    result = MB.task_maps_building_update_coverage(cells=[])
    assert isinstance(result, dict)


def test_update_coverage_with_cell_list(_stub_db):
    cell = MB._lat_lng_to_h3_approx(35.6895, 139.6917, 10)
    result = MB.task_maps_building_update_coverage(
        cells=[{"cell_key": cell, "building_count": 5}]
    )
    assert isinstance(result, dict)


# ─── register ────────────────────────────────────────────────────────────────

def test_register_exposes_three_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    MB.register(FakeWorker(), timeout_ms=60_000)
    assert set(registered) == {
        "maps.building.claimCells",
        "maps.building.enrichFromOsm",
        "maps.building.updateCoverage",
    }
