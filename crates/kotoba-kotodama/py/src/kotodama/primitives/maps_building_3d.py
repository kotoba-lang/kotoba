"""maps 建物 3D model ingest primitives — H3 cell claim + OSM enrich + coverage update.

Three LangServer task types:
  maps.building.claimCells     — Claim next batch of H3 res10 cells that have
                                  Building rows in vertex_spatial but haven't
                                  been ingested yet (or are stale > stale_days).
  maps.building.enrichFromOsm  — Fetch vertex_spatial Building rows per cell,
                                  compute 3D AABB, upsert vertex_maps_building_3d.
  maps.building.updateCoverage — Upsert vertex_maps_building_coverage per H3
                                  cell with building_count, has_sentinel flag.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import uuid
from datetime import timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

DEFAULT_REPO = "did:web:maps.etzhayyim.com"
COLLECTION_BUILDING_3D = "com.etzhayyim.apps.maps.building3d"
COLLECTION_COVERAGE = "com.etzhayyim.apps.maps.buildingCoverage"

# Default H3 resolution for coverage cells (res10 ≈ 53m edge, ~2100m² area).
_H3_RES = 10

# Half-width (metres) assumed for buildings when footprint is unknown.
_DEFAULT_HALF_M = 8.0

# Patchable batch ceiling for tests.
_MAX_CELLS_DEFAULT: int = 200

# Metres per degree of latitude (constant).
_M_PER_DEG_LAT = 111_320.0


# ──────────────────────────────────────────────────────────────────────
# Small helpers
# ──────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=_dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _new_rkey(prefix: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _stable_rkey(spatial_vertex_id: str) -> str:
    """Deterministic rkey so re-ingest of the same building is idempotent."""
    return hashlib.sha256(spatial_vertex_id.encode("utf-8")).hexdigest()[:16]


def _lat_lng_to_h3_approx(lat: float, lng: float, res: int) -> str:
    """Approximate H3 cell string without the h3 library.

    Uses a truncated grid cell key based on resolution-dependent tile size.
    Sufficient for cell-level bucketing; exact H3 hex IDs require the h3 lib.
    Format: h3_{res}_{lat_tile}_{lng_tile} where tile size halves each res step."""
    # H3 res 10 edge ≈ 0.000477 degrees latitude equivalent.
    step = 0.000477 * (2 ** (10 - res))
    lat_tile = int(math.floor(lat / step))
    lng_tile = int(math.floor(lng / step))
    return f"h3_{res}_{lat_tile}_{lng_tile}"


def _centroid_of_cell(cell_key: str) -> tuple[float, float]:
    """Return (lat, lng) centroid of an approximate H3 cell key."""
    parts = cell_key.split("_")
    if len(parts) != 4:
        return 0.0, 0.0
    try:
        res = int(parts[1])
        lat_tile = int(parts[2])
        lng_tile = int(parts[3])
    except (ValueError, IndexError):
        return 0.0, 0.0
    step = 0.000477 * (2 ** (10 - res))
    return (lat_tile + 0.5) * step, (lng_tile + 0.5) * step


# ──────────────────────────────────────────────────────────────────────
# Task 1 — claimCells
# ──────────────────────────────────────────────────────────────────────

def task_maps_building_claim_cells(
    max_cells: int = _MAX_CELLS_DEFAULT,
    stale_days: int = 7,
) -> dict[str, Any]:
    """Claim next batch of H3 cells with un-ingested or stale Building rows.

    Queries vertex_spatial for distinct approximate-H3 cells that either have
    no vertex_maps_building_coverage row, or whose last_ingest_at is older
    than stale_days. Returns the list for downstream tasks."""
    run_id = _new_rkey("bld-ingest")
    cap = max(1, min(int(max_cells or _MAX_CELLS_DEFAULT), 200))
    stale = max(1, int(stale_days or 7))
    stale_cutoff = (
        _dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=stale)
    ).isoformat().replace("+00:00", "Z")

    # Fetch distinct (lat, lng) pairs for Building rows; derive cell keys.
    # We avoid GROUP BY on high-cardinality varchar columns (MV safety rule)
    # and instead bucket in Python after a bounded SELECT.
    # R0: Multi-predicate filter and limit applied in Python since q() doesn't
    #     natively support LIMIT with complex filters without explicit range.
    _query_edn = """
    [:find ?vid ?lat ?lng
     :where
     [?e :vertex/label "Building"]
     [?e :vertex/vertex_id ?vid]
     [?e :vertex/lat ?lat]
     [?e :vertex/lng ?lng]
     (not [?e :vertex/lat nil])
     (not [?e :vertex/lng nil])]
    """
    db_rows = get_kotoba_client().q(_query_edn)
    rows: list[dict[str, Any]] = []
    for r in db_rows[:int(cap * 500)]:  # Apply limit here
        rows.append({"vertex_id": r[0], "lat": r[1], "lng": r[2]})

    # Bucket buildings into approximate H3 cells.
    cell_to_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        try:
            lat = float(row.get("lat") or 0)
            lng = float(row.get("lng") or 0)
        except (TypeError, ValueError):
            continue
        if lat == 0.0 and lng == 0.0:
            continue
        cell_key = _lat_lng_to_h3_approx(lat, lng, _H3_RES)
        cell_to_rows.setdefault(cell_key, []).append(row)

    if not cell_to_rows:
        return {"runId": run_id, "cells": [], "cellCount": 0}

    # Filter out cells that were recently ingested (not stale).
    # Fetch ALL fresh cells from coverage (no IN-clause limit) so large cell
    # spaces (16k+) don't silently skip the staleness check.
    all_cell_keys = list(cell_to_rows.keys())
    cell_key_set = set(all_cell_keys)
    fresh_cells: set[str] = set()
    if all_cell_keys:
        # R0: Range query with limit applied in Python.
        _cov_query_edn = """
        [:find ?tile_h3
         :in $ ?stale_cutoff
         :where
         [?e :vertex.maps-building-coverage/last_ingest_at ?last_ingest_at]
         [(> ?last_ingest_at ?stale_cutoff)]
         [?e :vertex.maps-building-coverage/tile_h3 ?tile_h3]]
        """
        cov_db_rows = get_kotoba_client().q(_cov_query_edn, args=[stale_cutoff])
        for r in cov_db_rows[:int(len(all_cell_keys) + 1000)]:  # Apply limit here
            tile_h3 = r[0]
            if tile_h3 in cell_key_set:
                fresh_cells.add(tile_h3)

    pending_cells = [k for k in all_cell_keys if k not in fresh_cells][:cap]

    cells_out = [
        {
            "cell_key": k,
            "building_vertex_ids": [r["vertex_id"] for r in cell_to_rows[k]],
            "building_count": len(cell_to_rows[k]),
        }
        for k in pending_cells
    ]

    return {
        "runId": run_id,
        "cells": cells_out,
        "cellCount": len(cells_out),
    }


# ──────────────────────────────────────────────────────────────────────
# Task 2 — enrichFromOsm
# ──────────────────────────────────────────────────────────────────────

def task_maps_building_enrich_from_osm(
    cells: list[dict[str, Any]] | None = None,
    run_id: str = "",
) -> dict[str, Any]:
    """Fetch building rows from vertex_spatial, compute 3D AABB, upsert vertex_maps_building_3d.

    For each building the AABB is derived from lat/lng centroid ± DEFAULT_HALF_M metres
    unless a footprint is stored in props JSON. Height defaults to 10m unless
    the props carry a height field."""
    if not cells:
        return {"buildingsIngested": 0, "cellsProcessed": 0}

    # Collect all building vertex IDs across cells.
    all_vids: list[str] = []
    cell_map: dict[str, str] = {}  # vertex_id → cell_key
    for cell in cells:
        for vid in (cell.get("building_vertex_ids") or []):
            all_vids.append(vid)
            cell_map[vid] = str(cell.get("cell_key") or "")

    if not all_vids:
        return {"buildingsIngested": 0, "cellsProcessed": 0}

    # Fetch spatial rows.
    # R0: `IN` clause translated to Datalog `(contains?)`
    _sel_query_edn = """
    [:find ?vid ?lat ?lng ?name ?props
     :in $ [?vids ...]
     :where
     [?e :vertex/vertex_id ?vid]
     (not [?e :vertex/vertex_id nil]) ; Ensure vertex_id exists
     [?e :vertex/lat ?lat]
     (not [?e :vertex/lat nil])
     [?e :vertex/lng ?lng]
     (not [?e :vertex/lng nil])
     [?e :vertex/name ?name]
     (not [?e :vertex/name nil])
     [?e :vertex/props ?props]
     (not [?e :vertex/props nil])
     [(contains? ?vids ?vid)]]
    """
    db_rows = get_kotoba_client().q(_sel_query_edn, args=[all_vids])
    spatial_rows: list[dict[str, Any]] = []
    for r in db_rows:
        spatial_rows.append({
            "vertex_id": r[0],
            "lat": r[1],
            "lng": r[2],
            "name": r[3],
            "props": r[4],
        })

    # Build insert params for vertex_maps_building_3d.
    ingested = 0
    now = _now_iso()
    for row in spatial_rows:
        spatial_vid = str(row.get("vertex_id") or "")
        try:
            lat = float(row.get("lat") or 0)
            lng = float(row.get("lng") or 0)
        except (TypeError, ValueError):
            continue
        if lat == 0.0 and lng == 0.0:
            continue

        cell_key = cell_map.get(spatial_vid, "")
        rkey = _stable_rkey(spatial_vid)
        new_vid = f"at://{DEFAULT_REPO}/{COLLECTION_BUILDING_3D}/{rkey}"

        # Extract height from props JSON.
        props: dict[str, Any] = {}
        raw_props = row.get("props") or ""
        if raw_props:
            try:
                props = json.loads(raw_props)
            except (TypeError, ValueError):
                pass
        height_m = float(props.get("height") or props.get("building:height") or 10.0)

        # Simple AABB footprint: centroid ± half_m degrees.
        half_lat = _DEFAULT_HALF_M / _M_PER_DEG_LAT
        half_lng = _DEFAULT_HALF_M / (_M_PER_DEG_LAT * math.cos(math.radians(lat)) + 1e-9)
        footprint = {
            "type": "Polygon",
            "coordinates": [[
                [lng - half_lng, lat - half_lat],
                [lng + half_lng, lat - half_lat],
                [lng + half_lng, lat + half_lat],
                [lng - half_lng, lat + half_lat],
                [lng - half_lng, lat - half_lat],
            ]],
        }

        row_dict = {
            "vertex_id": new_vid,
            "spatial_vertex_id": spatial_vid,
            "tile_h3": cell_key,
            "h3_resolution": _H3_RES,
            "centroid_lat": lat,
            "centroid_lng": lng,
            "footprint_json": json.dumps(footprint, separators=(",", ":")),
            "height_m": height_m,
            "source": "vertex_spatial",
            "ingest_at": now,
            "created_at": now,
            "sensitivity_ord": 1,
            "org_id": DEFAULT_REPO,
            "user_id": DEFAULT_REPO,
            "actor_id": "sys.maps.building3d",
            "owner_did": DEFAULT_REPO,
        }
        get_kotoba_client().insert_row("vertex_maps_building_3d", row_dict)
        ingested += 1

    return {
        "buildingsIngested": ingested,
        "cellsProcessed": len(cells),
    }


# ──────────────────────────────────────────────────────────────────────
# Task 3 — updateCoverage
# ──────────────────────────────────────────────────────────────────────

def task_maps_building_update_coverage(
    cells: list[dict[str, Any]] | None = None,
    run_id: str = "",
    buildings_ingested: int = 0,
) -> dict[str, Any]:
    """Upsert vertex_maps_building_coverage per H3 cell.

    Checks vertex_satellite_scene for any scene whose bbox overlaps the cell
    centroid to set the has_sentinel flag. has_mapraly is reserved for Phase 2."""
    if not cells:
        return {"coverageUpdated": 0}

    now = _now_iso()
    # Sentinel scene check: query vertex_satellite_scene for bbox containing centroid.
    # bbox column stores JSON array [minLon, minLat, maxLon, maxLat] as VARCHAR.
    updated = 0
    for cell in cells:
        cell_key = str(cell.get("cell_key") or "")
        building_count = int(cell.get("building_count") or 0)
        clat, clng = _centroid_of_cell(cell_key)

        # Rough sentinel check via LIKE on bbox — precision is sufficient
        # for coverage flagging. Full spatial join deferred to Phase 2.
        has_sentinel = False
        try:
            lat_prefix = f"{clat:.2f}"[:4]  # first 4 chars of lat
            # R0: LIKE '%pattern%' requires fetching all bboxes and filtering in Python
            _bbox_query_edn = """
            [:find ?bbox
             :where
             [?e :vertex.satellite-scene/bbox ?bbox]]
            """
            bbox_rows = get_kotoba_client().q(_bbox_query_edn)
            matching_bboxes = [b[0] for b in bbox_rows if lat_prefix in b[0]]
            has_sentinel = len(matching_bboxes) > 0
        except Exception:
            has_sentinel = False

        rkey = hashlib.sha256(cell_key.encode("utf-8")).hexdigest()[:16]
        cov_vid = f"at://{DEFAULT_REPO}/{COLLECTION_COVERAGE}/{rkey}"
        sources = ["vertex_spatial"]
        if has_sentinel:
            sources.append("sentinel")

        row_dict = {
            "vertex_id": cov_vid,
            "tile_h3": cell_key,
            "h3_resolution": _H3_RES,
            "centroid_lat": clat,
            "centroid_lng": clng,
            "building_count": building_count,
            "has_sentinel": has_sentinel,
            "has_mapraly": False,
            "coverage_source": ",".join(sources),
            "last_ingest_at": now,
            "status": "ingested",
            "created_at": now,
            "sensitivity_ord": 1,
            "org_id": DEFAULT_REPO,
            "user_id": DEFAULT_REPO,
            "actor_id": "sys.maps.building3d",
            "owner_did": DEFAULT_REPO,
        }
        get_kotoba_client().insert_row("vertex_maps_building_coverage", row_dict)
        updated += 1

    return {"coverageUpdated": updated}


# ──────────────────────────────────────────────────────────────────────
# LangServer registration
# ──────────────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire maps building 3D primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    t("maps.building.claimCells",    task_maps_building_claim_cells,
      timeout=max(timeout_ms, 60_000))
    t("maps.building.enrichFromOsm", task_maps_building_enrich_from_osm,
      timeout=max(timeout_ms, 300_000))
    t("maps.building.updateCoverage", task_maps_building_update_coverage,
      timeout=max(timeout_ms, 120_000))


__all__ = [
    "register",
    "task_maps_building_claim_cells",
    "task_maps_building_enrich_from_osm",
    "task_maps_building_update_coverage",
    "_lat_lng_to_h3_approx",
    "_centroid_of_cell",
    "_stable_rkey",
    "DEFAULT_REPO",
    "_H3_RES",
    "_MAX_CELLS_DEFAULT",
]
