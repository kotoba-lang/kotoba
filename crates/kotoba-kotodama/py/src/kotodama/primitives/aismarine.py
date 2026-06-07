"""maps AIS Marine vessel-tracking primitives — MarineTraffic-equivalent.

ADR-2605011500. Phase 1: aisstream.io WebSocket consumer + voyage detector
+ master refresh + bbox query. Writes to typed tables vertex_vessel /
vertex_vessel_position / vertex_vessel_voyage / edge_vessel_visited_port
via sync_cursor (Worker-direct Hyperdrive pattern, ADR-0036).

LangServer task types:
  aismarine.position.batchInsert    — flush a batch of decoded AIS positions.
  aismarine.master.upsert           — upsert vessel master rows from Type-5 broadcasts.
  aismarine.voyage.detectWindow     — scan recent positions, derive voyages.
  aismarine.master.refresh          — backfill flag_iso / dimensions for stale rows.
  aismarine.density.verify          — observability check on density MV.
  aismarine.query.bbox              — read-only bbox query (XRPC-backed).

The long-running aisstream.io WebSocket consumer lives in
50-infra/vultr/bulk-ingest/aismarine-consumer/ (K8s Deployment) and is wired
in zeebe_worker_main when AISMARINE_CONSUMER_MODE=1 — it reuses the same
psycopg pool but does not register as a LangServer task.

Conventions enforced:
- flush=False on every INSERT (CLAUDE.md 2026-04-30 yoro fix)
- LIMIT {int(n)} string interpolation (rw-psycopg3-no-param-limit)
- No ON CONFLICT (RW PK implicit upsert)
- SET dml_rate_limit before bulk INSERT (ADR-0048 incident_2026_04_25)
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import json
import math
import os
import time
from typing import Any


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

DEFAULT_REPO = "did:web:maps.etzhayyim.com"
SOURCE_AISSTREAM = "aisstream"

_VALID_TYPE_CLASSES = {
    "cargo", "tanker", "passenger", "highspeed", "sailing_pleasure",
    "fishing", "tug", "military", "pilot", "sar", "lawenforcement",
    "other", "unknown",
}

# AIS port-proximity threshold (km). Vessel within this radius of a port
# centroid + nav_status ∈ {1,5,15} → arrival.
_VOYAGE_PORT_RADIUS_KM = 5.0

# Patchable for tests.
_BULK_DML_RATE_LIMIT = 5000  # rows/sec/parallelism (RW INSERT throttle)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(time.time() * 1000)


def _today_iso_date() -> str:
    return _dt.date.today().isoformat()


def _vessel_vid(mmsi: int) -> str:
    return f"mmsi:{int(mmsi)}"


def _position_vid(mmsi: int, ts_ms: int) -> str:
    return f"mmsi:{int(mmsi)}:ts:{int(ts_ms)}"


def _voyage_vid(mmsi: int, departure_ms: int) -> str:
    return f"mmsi:{int(mmsi)}:voy:{int(departure_ms)}"


def _visited_edge_id(mmsi: int, locode: str, arrival_ms: int) -> str:
    return f"mmsi:{int(mmsi)}:port:{locode}:arr:{int(arrival_ms)}"


def _coerce_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _coerce_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ──────────────────────────────────────────────────────────────────────
# Position batch INSERT — invoked by the K8s consumer + ingestAisStream NSID
# ──────────────────────────────────────────────────────────────────────

def task_aismarine_position_batch_insert(
    positions: list[dict] | None = None,
    flush: bool = False,
) -> dict[str, Any]:
    """INSERT a batch of decoded AIS positions into vertex_vessel_position.

    Each row: { mmsi, ts_ms, lat, lon, sog_knot?, cog_deg?, heading_deg?,
                nav_status?, source? }. Bad rows are silently dropped (the
                consumer is upstream of all validation and AIS messages are
                routinely garbage). source defaults to 'aisstream'.

    Returns: { ok, rows_inserted, rows_dropped }.
    """
    rows = positions or []
    if not isinstance(rows, list) or not rows:
        return {"ok": True, "rows_inserted": 0, "rows_dropped": 0}

    today = _today_iso_date()
    valid_rows: list[tuple] = []
    dropped = 0

    for r in rows:
        if not isinstance(r, dict):
            dropped += 1
            continue
        mmsi = _coerce_int(r.get("mmsi"))
        ts_ms = _coerce_int(r.get("ts_ms"))
        lat = _coerce_float(r.get("lat"))
        lon = _coerce_float(r.get("lon"))
        if mmsi is None or ts_ms is None or lat is None or lon is None:
            dropped += 1
            continue
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            dropped += 1
            continue
        valid_rows.append((
            _position_vid(mmsi, ts_ms),
            today,
            mmsi,
            ts_ms,
            lat,
            lon,
            _coerce_float(r.get("sog_knot")),
            _coerce_float(r.get("cog_deg")),
            _coerce_int(r.get("heading_deg")),
            _coerce_int(r.get("nav_status")),
            str(r.get("source") or SOURCE_AISSTREAM),
        ))

    if not valid_rows:
        return {"ok": True, "rows_inserted": 0, "rows_dropped": dropped}

    if True:

        client = get_kotoba_client()
        # ADR-0048 incident_2026_04_25: throttle bulk INSERT
        _res = client.q(f"SET dml_rate_limit = {int(_BULK_DML_RATE_LIMIT)}")
        _res = client.q(
            """
            INSERT INTO vertex_vessel_position
              (vertex_id, created_date, mmsi, ts_ms, lat, lon,
               sog_knot, cog_deg, heading_deg, nav_status, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            valid_rows,
        )
        if flush:
            _res = client.q("FLUSH")

    return {"ok": True, "rows_inserted": len(valid_rows), "rows_dropped": dropped}


# ──────────────────────────────────────────────────────────────────────
# Vessel master upsert — Type-5 broadcasts
# ──────────────────────────────────────────────────────────────────────

def task_aismarine_master_upsert(
    masters: list[dict] | None = None,
    flush: bool = False,
) -> dict[str, Any]:
    """UPSERT vessel master rows.

    Each row: { mmsi, imo?, callsign?, name?, type_code?, length_m?,
                width_m?, draught_m?, source?, ts_ms? }.

    Strategy: SELECT current row → merge non-null fields → re-INSERT (PK
    overwrite, RW implicit upsert). first_seen_ms is preserved across upserts;
    last_seen_ms moves forward.
    """
    rows = masters or []
    if not isinstance(rows, list) or not rows:
        return {"ok": True, "rows_upserted": 0}

    today = _today_iso_date()
    upserted = 0

    if True:

        client = get_kotoba_client()
        _res = client.q(f"SET dml_rate_limit = {int(_BULK_DML_RATE_LIMIT)}")
        for r in rows:
            if not isinstance(r, dict):
                continue
            mmsi = _coerce_int(r.get("mmsi"))
            if mmsi is None:
                continue
            ts_ms = _coerce_int(r.get("ts_ms")) or _now_ms()
            vid = _vessel_vid(mmsi)

            _res = client.q(
                """
                SELECT imo, callsign, name, type_code, length_m, width_m,
                       draught_m, first_seen_ms
                FROM vertex_vessel
                WHERE vertex_id = %s
                LIMIT 1
                """,
                (vid,),
            )
            existing = (_res[0] if _res else None)

            imo = _coerce_int(r.get("imo"))
            callsign = r.get("callsign")
            name = r.get("name")
            type_code = _coerce_int(r.get("type_code"))
            length_m = _coerce_float(r.get("length_m"))
            width_m = _coerce_float(r.get("width_m"))
            draught_m = _coerce_float(r.get("draught_m"))

            if existing is not None:
                imo = imo if imo is not None else existing[0]
                callsign = callsign if callsign else existing[1]
                name = name if name else existing[2]
                type_code = type_code if type_code is not None else existing[3]
                length_m = length_m if length_m is not None else existing[4]
                width_m = width_m if width_m is not None else existing[5]
                draught_m = draught_m if draught_m is not None else existing[6]
                first_seen_ms = existing[7] or ts_ms
            else:
                first_seen_ms = ts_ms

            mid = mmsi // 1_000_000 if 200_000_000 <= mmsi <= 799_999_999 else None
            _res = client.q(
                """
                INSERT INTO vertex_vessel
                  (vertex_id, created_date, mmsi, imo, callsign, name,
                   type_code, type_class, flag_mid, flag_iso,
                   length_m, width_m, draught_m, source,
                   first_seen_ms, last_seen_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                        vessel_type_class(%s), %s, vessel_flag_iso(%s),
                        %s, %s, %s, %s, %s, %s)
                """,
                (
                    vid, today, mmsi, imo, callsign, name,
                    type_code, type_code, mid, mmsi,
                    length_m, width_m, draught_m,
                    str(r.get("source") or SOURCE_AISSTREAM),
                    first_seen_ms, ts_ms,
                ),
            )
            upserted += 1

        if flush:
            _res = client.q("FLUSH")

    return {"ok": True, "rows_upserted": upserted}


# ──────────────────────────────────────────────────────────────────────
# Voyage detector
# ──────────────────────────────────────────────────────────────────────

# AIS nav_status that signal moored/anchored (= candidate arrival) when
# the vessel sits within port radius. 1=anchored, 5=moored, 15=undefined
# but commonly used by smaller fleets for "stopped".
_ARRIVAL_NAV_STATUSES = (1, 5, 15)


def task_aismarine_voyage_detect_window(
    window_minutes: int = 5,
    limit: int = 50000,
) -> dict[str, Any]:
    """Scan the last ``window_minutes`` of vertex_vessel_position, detect
    arrivals/departures by joining against vertex_open_ports_port (UN/LOCODE
    coordinates), and write derived rows.

    Arrival heuristic: nav_status ∈ {1,5,15} AND haversine(pos, port) <= 5km.
    Open-voyage rows (departure_ms set, arrival_ms NULL) get arrival_ms +
    arrival_port_locode populated. Closed-voyage rows are immutable.

    Returns: { ok, scanned, arrivals_recorded, voyages_opened }.
    """
    if window_minutes <= 0:
        window_minutes = 5
    cutoff_ms = _now_ms() - int(window_minutes) * 60_000
    today = _today_iso_date()

    arrivals = 0
    opened = 0

    if True:

        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT mmsi, ts_ms, lat, lon, nav_status, sog_knot
            FROM vertex_vessel_position
            WHERE ts_ms >= %s
            ORDER BY mmsi, ts_ms ASC
            LIMIT {int(limit)}
            """,
            (cutoff_ms,),
        )
        positions = _res

        if not positions:
            return {"ok": True, "scanned": 0, "arrivals_recorded": 0, "voyages_opened": 0}

        # Pull active ports once. Port count globally ~17K (vertex_open_ports_port);
        # the in-memory radius scan is faster than per-position SQL JOIN here.
        _res = client.q(
            """
            SELECT vertex_id, un_locode, latitude, longitude
            FROM vertex_open_ports_port
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """
        )
        ports = _res

    if not ports:
        return {"ok": True, "scanned": len(positions), "arrivals_recorded": 0, "voyages_opened": 0}

    def _nearest_port(lat: float, lon: float) -> tuple[str, str, float] | None:
        best: tuple[str, str, float] | None = None
        for p_vid, p_locode, p_lat, p_lon in ports:
            if p_lat is None or p_lon is None or not p_locode:
                continue
            d = _haversine_km(lat, lon, float(p_lat), float(p_lon))
            if d > _VOYAGE_PORT_RADIUS_KM:
                continue
            if best is None or d < best[2]:
                best = (p_vid, p_locode, d)
        return best

    if True:

        client = get_kotoba_client()
        for row in positions:
            mmsi, ts_ms, lat, lon, nav_status, sog_knot = row
            mmsi = int(mmsi)
            ts_ms = int(ts_ms)
            if nav_status is None or int(nav_status) not in _ARRIVAL_NAV_STATUSES:
                continue
            if sog_knot is not None and float(sog_knot) > 0.5:
                continue
            near = _nearest_port(float(lat), float(lon))
            if near is None:
                continue
            port_vid, locode, _dist = near

            # Find open voyage (departure_ms set, arrival_ms NULL, latest).
            _res = client.q(
                """
                SELECT vertex_id, departure_ms
                FROM vertex_vessel_voyage
                WHERE mmsi = %s AND arrival_ms IS NULL
                ORDER BY departure_ms DESC NULLS LAST
                LIMIT 1
                """,
                (mmsi,),
            )
            open_voy = (_res[0] if _res else None)

            if open_voy is not None and open_voy[1] is not None:
                voy_vid = open_voy[0]
                _res = client.q(
                    """
                    UPDATE vertex_vessel_voyage
                    SET arrival_ms = %s, arrival_port_locode = %s
                    WHERE vertex_id = %s
                    """,
                    (ts_ms, locode, voy_vid),
                )
                arrivals += 1
            else:
                # No open voyage: open a new one anchored at this arrival
                # (departure unknown). Convention: departure_ms = ts_ms,
                # arrival_ms = ts_ms — represents a single port-call ping.
                voy_vid = _voyage_vid(mmsi, ts_ms)
                _res = client.q(
                    """
                    INSERT INTO vertex_vessel_voyage
                      (vertex_id, created_date, mmsi,
                       departure_port_locode, departure_ms,
                       arrival_port_locode, arrival_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (voy_vid, today, mmsi, locode, ts_ms, locode, ts_ms),
                )
                opened += 1

            _res = client.q(
                """
                INSERT INTO edge_vessel_visited_port
                  (edge_id, created_date, src_vid, dst_vid,
                   mmsi, port_locode, arrival_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    _visited_edge_id(mmsi, locode, ts_ms),
                    today,
                    _vessel_vid(mmsi),
                    port_vid,
                    mmsi,
                    locode,
                    ts_ms,
                ),
            )

    return {
        "ok": True,
        "scanned": len(positions),
        "arrivals_recorded": arrivals,
        "voyages_opened": opened,
    }


# ──────────────────────────────────────────────────────────────────────
# Master refresh — open-data only flag/dimension backfill
# ──────────────────────────────────────────────────────────────────────

def task_aismarine_master_refresh(limit: int = 5000) -> dict[str, Any]:
    """Backfill flag_iso / type_class for vertex_vessel rows that are missing
    them, using the SQL UDFs vessel_flag_iso(mmsi) and vessel_type_class(type_code).
    Open-data only — no external IHS / VT Explorer fetch (ADR-2605011500).
    """
    if limit <= 0:
        limit = 5000
    if limit > 50000:
        limit = 50000

    if True:

        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT vertex_id, mmsi, type_code
            FROM vertex_vessel
            WHERE flag_iso IS NULL OR type_class IS NULL OR type_class = 'unknown'
            LIMIT {int(limit)}
            """
        )
        rows = _res

        if not rows:
            return {"ok": True, "rows_scanned": 0, "rows_updated": 0}

        _res = client.q(f"SET dml_rate_limit = {int(_BULK_DML_RATE_LIMIT)}")
        for vid, mmsi, type_code in rows:
            _res = client.q(
                """
                UPDATE vertex_vessel
                SET flag_iso = vessel_flag_iso(%s),
                    flag_mid = CASE WHEN %s BETWEEN 200000000 AND 799999999
                                    THEN (%s / 1000000)::smallint
                                    ELSE flag_mid END,
                    type_class = vessel_type_class(%s)
                WHERE vertex_id = %s
                """,
                (int(mmsi), int(mmsi), int(mmsi), type_code, vid),
            )

    return {"ok": True, "rows_scanned": len(rows), "rows_updated": len(rows)}


# ──────────────────────────────────────────────────────────────────────
# Density verify (observability)
# ──────────────────────────────────────────────────────────────────────

def task_aismarine_density_verify() -> dict[str, Any]:
    """Sanity-check mv_vessel_density_h3_r6. The MV is autonomous (streaming),
    so this is observability only — counts rows + reports the latest bucket.
    """
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT COUNT(*) FROM mv_vessel_density_h3_r6")
        row_count = (_res[0] if _res else None)
        _res = client.q("SELECT MAX(bucket_ms) FROM mv_vessel_density_h3_r6")
        max_bucket = (_res[0] if _res else None)
    return {
        "ok": True,
        "row_count": int(row_count[0]) if row_count and row_count[0] is not None else 0,
        "latest_bucket_ms": int(max_bucket[0]) if max_bucket and max_bucket[0] is not None else None,
    }


# ──────────────────────────────────────────────────────────────────────
# Bbox query — read path for com.etzhayyim.apps.maps.aismarine.queryVesselsBbox
# ──────────────────────────────────────────────────────────────────────

def task_aismarine_query_bbox(
    bbox: list[float] | None = None,
    types: list[str] | None = None,
    min_sog: float | None = None,
    limit: int = 5000,
) -> dict[str, Any]:
    """Return latest position per MMSI inside ``bbox`` as a GeoJSON
    FeatureCollection. Backed by mv_vessel_latest_position JOIN vertex_vessel.

    bbox = [west, south, east, north] in WGS84 degrees.
    """
    if not isinstance(bbox, list) or len(bbox) != 4:
        return {"features": [], "total": 0, "bbox": bbox or [], "truncated": False}
    try:
        w, s, e, n = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    except (TypeError, ValueError):
        return {"features": [], "total": 0, "bbox": bbox, "truncated": False}

    if limit <= 0:
        limit = 5000
    if limit > 20000:
        limit = 20000

    type_classes: list[str] = []
    if isinstance(types, list):
        for t in types:
            if isinstance(t, str) and t in _VALID_TYPE_CLASSES:
                type_classes.append(t)

    # Antimeridian crossing: w > e means the bbox wraps (e.g. w=170, e=-170).
    where_lon = "(p.lon BETWEEN %s AND %s)" if w <= e else "(p.lon >= %s OR p.lon <= %s)"
    params: list[Any] = [s, n, w, e]

    sql_parts = [
        "SELECT p.mmsi, p.ts_ms, p.lat, p.lon, p.sog_knot, p.cog_deg,",
        "       p.heading_deg, p.nav_status,",
        "       v.name, v.type_code, v.type_class, v.flag_iso",
        "FROM mv_vessel_latest_position p",
        "LEFT JOIN vertex_vessel v ON v.mmsi = p.mmsi",
        "WHERE p.lat BETWEEN %s AND %s",
        f"  AND {where_lon}",
    ]
    if min_sog is not None:
        sql_parts.append("  AND p.sog_knot >= %s")
        params.append(float(min_sog))
    if type_classes:
        placeholders = ",".join(["%s"] * len(type_classes))
        sql_parts.append(f"  AND v.type_class IN ({placeholders})")
        params.extend(type_classes)
    sql_parts.append(f"LIMIT {int(limit) + 1}")
    sql = "\n".join(sql_parts)

    if True:

        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        rows = _res

    truncated = len(rows) > limit
    if truncated:
        rows = rows[:limit]

    features = []
    for r in rows:
        mmsi, ts_ms, lat, lon, sog, cog, heading, nav, name, type_code, type_class, flag_iso = r
        props: dict[str, Any] = {
            "mmsi": int(mmsi),
            "ts_ms": int(ts_ms),
            "type_class": type_class or "unknown",
        }
        if name:
            props["name"] = name
        if type_code is not None:
            props["type_code"] = int(type_code)
        if flag_iso:
            props["flag_iso"] = flag_iso
        if sog is not None:
            props["sog_knot"] = float(sog)
        if cog is not None:
            props["cog_deg"] = float(cog)
        if heading is not None:
            props["heading_deg"] = int(heading)
        if nav is not None:
            props["nav_status"] = int(nav)

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": props,
        })

    return {
        "features": features,
        "total": len(features),
        "bbox": [w, s, e, n],
        "truncated": truncated,
    }


# ──────────────────────────────────────────────────────────────────────
# LangServer registration
# ──────────────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire aismarine primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    t("aismarine.position.batchInsert", task_aismarine_position_batch_insert,
      timeout=max(timeout_ms, 30_000))
    t("aismarine.master.upsert", task_aismarine_master_upsert,
      timeout=max(timeout_ms, 60_000))
    t("aismarine.voyage.detectWindow", task_aismarine_voyage_detect_window,
      timeout=max(timeout_ms, 240_000))
    t("aismarine.master.refresh", task_aismarine_master_refresh,
      timeout=max(timeout_ms, 240_000))
    t("aismarine.density.verify", task_aismarine_density_verify,
      timeout=max(timeout_ms, 30_000))
    t("aismarine.query.bbox", task_aismarine_query_bbox,
      timeout=max(timeout_ms, 30_000))


__all__ = [
    "register",
    "task_aismarine_position_batch_insert",
    "task_aismarine_master_upsert",
    "task_aismarine_voyage_detect_window",
    "task_aismarine_master_refresh",
    "task_aismarine_density_verify",
    "task_aismarine_query_bbox",
    "_haversine_km",
    "_vessel_vid",
    "_position_vid",
    "_voyage_vid",
    "_visited_edge_id",
    "_VOYAGE_PORT_RADIUS_KM",
    "_BULK_DML_RATE_LIMIT",
    "_ARRIVAL_NAV_STATUSES",
    "DEFAULT_REPO",
    "SOURCE_AISSTREAM",
]
