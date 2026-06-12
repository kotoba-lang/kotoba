"""maps live aircraft primitives — Flightradar24-equivalent state ingest.

ADR-0036 (worker-direct Hyperdrive) + ADR-0056 (BPMN-as-actor).

Two LangServer task types:
  flight.live.poll       — single OpenSky /states/all GET (12k aircraft global),
                            optional adsb-fi fallback on 429, writes
                            vertex_aircraft_state via sync_cursor.
  flight.track.compact   — group last N seconds of state vectors per icao24,
                            build LineString GeoJSON, write vertex_aircraft_track.

OpenSky retired previously due to bbox-tile drift (migration
20260424390000_purge_unsupported_dead_targets.ts). This implementation uses
single global /states/all (no tile composition) so drift is impossible.

RisingWave constraints honored:
  - no ON CONFLICT (use idempotent PK upsert; same vertex_id = overwrite per [[conventions]] rw-implicit-upsert)
  - psycopg3 LIMIT $N forbidden in prepared statements
    (lint convention rw-psycopg3-no-param-limit) → inline integer literal.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

DEFAULT_REPO = "did:web:maps.etzhayyim.com"
ACTOR_DID = "did:web:maps.etzhayyim.com:flightradar"

OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
OPENSKY_TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
ADSBFI_STATES_URL = "https://opendata.adsb.fi/api/v2/snapshot"  # community fallback

# Process-wide OAuth2 token cache. OpenSky tokens last ~30min; we refresh
# on first miss + ~5min before expiry.
_OPENSKY_TOKEN: dict[str, Any] = {"access_token": "", "expires_at_ms": 0}

# OpenSky /states/all column order (17 cols, 18 with category in extended).
# https://openskynetwork.github.io/opensky-api/rest.html#all-state-vectors
_OPENSKY_COLS = [
    "icao24", "callsign", "origin_country", "time_position", "last_contact",
    "longitude", "latitude", "baro_altitude", "on_ground", "velocity",
    "true_track", "vertical_rate", "sensors", "geo_altitude", "squawk",
    "spi", "position_source",
]

# ──────────────────────────────────────────────────────────────────────
# Small helpers
# ──────────────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=_dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _new_run_id(prefix: str = "flight") -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _http_get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[int, Any | None]:
    h = {"accept": "application/json", "user-agent": "etzhayyim-maps-flightradar/1.0"}
    if headers:
        h.update(headers)
    req = Request(url, headers=h, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status_code = getattr(resp, "status", 200)
            try:
                return status_code, json.loads(raw)
            except (TypeError, ValueError):
                return status_code, None
    except HTTPError as e:
        return e.code, None
    except (URLError, OSError):
        return 0, None


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _b(v: Any) -> bool | None:
    if v is None:
        return None
    return bool(v)


def _s(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


# ──────────────────────────────────────────────────────────────────────
# OpenSky parsing
# ──────────────────────────────────────────────────────────────────────

def _opensky_bearer_token() -> str:
    """Return a fresh OAuth2 access token for the OpenSky API.

    Uses Keycloak client_credentials grant. Cached process-wide for the
    token lifetime minus a 5min safety buffer. Returns "" if env not set
    or the token endpoint is unreachable — caller falls back to anonymous.
    """
    cid = os.environ.get("OPENSKY_CLIENT_ID", "").strip()
    secret = os.environ.get("OPENSKY_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        return ""
    now_ms = _now_ms()
    if _OPENSKY_TOKEN["access_token"] and now_ms < int(_OPENSKY_TOKEN["expires_at_ms"]):
        return str(_OPENSKY_TOKEN["access_token"])
    body = (
        f"grant_type=client_credentials"
        f"&client_id={urllib.parse.quote(cid)}"
        f"&client_secret={urllib.parse.quote(secret)}"
    ).encode("utf-8")
    req = Request(
        OPENSKY_TOKEN_URL,
        data=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, OSError, ValueError):
        return ""
    tok = str(data.get("access_token") or "")
    expires_in = int(data.get("expires_in") or 0)
    if not tok or expires_in <= 0:
        return ""
    _OPENSKY_TOKEN["access_token"] = tok
    # Refresh 5 min before expiry to avoid mid-poll 401s.
    _OPENSKY_TOKEN["expires_at_ms"] = now_ms + max(60, expires_in - 300) * 1000
    return tok


def _opensky_state_to_row(state: list[Any], ingested_at_ms: int) -> dict[str, Any] | None:
    """Convert one OpenSky state-vector array to a vertex_aircraft_state row dict."""
    if not isinstance(state, list) or len(state) < 17:
        return None
    rec = dict(zip(_OPENSKY_COLS, state[:17]))
    icao24 = _s(rec["icao24"])
    if not icao24:
        return None
    last_contact = rec.get("last_contact")
    ts_ms = int(float(last_contact) * 1000) if last_contact else ingested_at_ms
    return {
        "icao24": icao24,
        "callsign": _s(rec.get("callsign")),
        "tail_number": None,
        "lat": _f(rec.get("latitude")),
        "lon": _f(rec.get("longitude")),
        "baro_altitude_m": _f(rec.get("baro_altitude")),
        "geo_altitude_m": _f(rec.get("geo_altitude")),
        "velocity_ms": _f(rec.get("velocity")),
        "heading_deg": _f(rec.get("true_track")),
        "vertical_rate_ms": _f(rec.get("vertical_rate")),
        "on_ground": _b(rec.get("on_ground")),
        "squawk": _s(rec.get("squawk")),
        "origin_country": _s(rec.get("origin_country")),
        "source": "opensky",
        "ts_ms": ts_ms,
        "ingested_at_ms": ingested_at_ms,
    }


def _adsbfi_aircraft_to_row(ac: dict[str, Any], ingested_at_ms: int) -> dict[str, Any] | None:
    """adsb.fi /snapshot ac entry → row. Schema differs from OpenSky."""
    if not isinstance(ac, dict):
        return None
    icao24 = _s(ac.get("hex"))
    if not icao24:
        return None
    seen = ac.get("seen") or 0
    ts_ms = ingested_at_ms - int(float(seen) * 1000)
    return {
        "icao24": icao24,
        "callsign": _s(ac.get("flight")),
        "tail_number": _s(ac.get("r")),
        "lat": _f(ac.get("lat")),
        "lon": _f(ac.get("lon")),
        "baro_altitude_m": (_f(ac.get("alt_baro")) or 0) * 0.3048 if ac.get("alt_baro") not in (None, "ground") else None,
        "geo_altitude_m": (_f(ac.get("alt_geom")) or 0) * 0.3048 if ac.get("alt_geom") is not None else None,
        "velocity_ms": (_f(ac.get("gs")) or 0) * 0.514444 if ac.get("gs") is not None else None,  # knots → m/s
        "heading_deg": _f(ac.get("track")),
        "vertical_rate_ms": (_f(ac.get("baro_rate")) or 0) * 0.00508 if ac.get("baro_rate") is not None else None,  # ft/min → m/s
        "on_ground": ac.get("alt_baro") == "ground",
        "squawk": _s(ac.get("squawk")),
        "origin_country": None,
        "source": "adsb-fi",
        "ts_ms": ts_ms,
        "ingested_at_ms": ingested_at_ms,
    }


# ──────────────────────────────────────────────────────────────────────
# DB writer
# ──────────────────────────────────────────────────────────────────────

_INSERT_STATE_SQL = """
INSERT INTO vertex_aircraft_state (
  vertex_id, icao24, callsign, tail_number, lat, lon,
  baro_altitude_m, geo_altitude_m, velocity_ms, heading_deg, vertical_rate_ms,
  on_ground, squawk, origin_country, source, ts_ms, ingested_at_ms,
  actor_did, org_did, sensitivity_ord, owner_did
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _insert_state_rows(rows: list[dict[str, Any]]) -> int:
    """Bulk-insert state vectors. Returns count written."""
    if not rows:
        return 0
    written = 0
    if True:
        client = get_kotoba_client()
        for row in rows:
            vertex_id = f"{row['icao24']}:{row['ts_ms']}"
            params = (
                vertex_id,
                row["icao24"], row["callsign"], row["tail_number"],
                row["lat"], row["lon"],
                row["baro_altitude_m"], row["geo_altitude_m"],
                row["velocity_ms"], row["heading_deg"], row["vertical_rate_ms"],
                row["on_ground"], row["squawk"], row["origin_country"],
                row["source"], row["ts_ms"], row["ingested_at_ms"],
                ACTOR_DID, "anon", 1, DEFAULT_REPO,
            )
            try:
                _res = client.q(_INSERT_STATE_SQL, params)
                written += 1
            except Exception:  # noqa: BLE001
                # PK collision on identical (icao24, ts_ms) — RW silently overwrites
                # but a rare driver-level error shouldn't kill the whole batch.
                continue
    return written


# ──────────────────────────────────────────────────────────────────────
# Task: flight.live.poll
# ──────────────────────────────────────────────────────────────────────

def task_flight_live_poll(bbox: Any = None) -> dict[str, Any]:
    """Poll OpenSky /states/all once, fall back to adsb.fi on 429/5xx.

    bbox kept for parity with seedAdsb stub but ignored — single global call
    avoids the bbox-tile drift that retired the previous implementation.
    """
    run_id = _new_run_id()
    ingested_at_ms = _now_ms()

    headers: dict[str, str] = {}
    bearer = _opensky_bearer_token()
    if bearer:
        headers["authorization"] = f"Bearer {bearer}"
    else:
        # Legacy Basic-auth fallback (pre-2024 OpenSky API; deprecated 2025).
        user = os.environ.get("OPENSKY_USERNAME", "").strip()
        pwd = os.environ.get("OPENSKY_PASSWORD", "").strip()
        if user and pwd:
            import base64
            headers["authorization"] = "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode()

    rows: list[dict[str, Any]] = []
    sourced_from = ""

    status, body = _http_get_json(OPENSKY_STATES_URL, headers=headers, timeout=15.0)
    if status == 200 and isinstance(body, dict):
        states = body.get("states") or []
        for st in states:
            row = _opensky_state_to_row(st, ingested_at_ms)
            if row is not None:
                rows.append(row)
        sourced_from = "opensky"

    if not rows:
        status2, body2 = _http_get_json(ADSBFI_STATES_URL, timeout=15.0)
        if status2 == 200 and isinstance(body2, dict):
            ac_list = body2.get("ac") or []
            for ac in ac_list:
                row = _adsbfi_aircraft_to_row(ac, ingested_at_ms)
                if row is not None:
                    rows.append(row)
            sourced_from = "adsb-fi"

    written = _insert_state_rows(rows)

    return {
        "runId": run_id,
        "rowsIngested": written,
        "sourcedFrom": sourced_from or "none",
        "ingestedAtMs": ingested_at_ms,
    }


# ──────────────────────────────────────────────────────────────────────
# Task: flight.track.compact
# ──────────────────────────────────────────────────────────────────────

_SELECT_RECENT_SQL_TPL = """
SELECT icao24, callsign, lat, lon, baro_altitude_m, velocity_ms, ts_ms
FROM vertex_aircraft_state
WHERE on_ground = false
  AND ts_ms >= %s
  AND lat IS NOT NULL AND lon IS NOT NULL
ORDER BY icao24, ts_ms ASC
LIMIT {limit}
"""

_INSERT_TRACK_SQL = """
INSERT INTO vertex_aircraft_track (
  vertex_id, icao24, callsign, flight_start_ms, flight_end_ms,
  origin_iata, dest_iata, path_geojson,
  max_altitude_m, max_velocity_ms, point_count,
  actor_did, org_did, sensitivity_ord, owner_did, created_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _build_linestring(points: list[tuple[float, float]]) -> str:
    """Emit GeoJSON LineString JSON-encoded as VARCHAR. Sample to ≤500 points."""
    n = len(points)
    if n == 0:
        return ""
    if n > 500:
        step = n // 500 + 1
        points = points[::step]
    coords = [[lon, lat] for lat, lon in points]
    return json.dumps({"type": "LineString", "coordinates": coords}, separators=(",", ":"))


def _nearest_airport_iata(cur: Any, lat: float, lon: float, max_radius_deg: float = 0.5) -> str | None:
    """Find nearest airport IATA code within ~55 km (0.5° lat/lon box).

    Reads from vertex_spatial WHERE label='Airport'. Iata code is stored
    in `props` JSON or as `airport_code` typed column depending on ingest path
    (OurAirports CSV pipeline). We try both.
    """
    sql = """
    SELECT
      COALESCE(airport_code, props->>'iata', props->>'iata_code') AS iata,
      lat,
      lng
    FROM vertex_spatial
    WHERE label = 'Airport'
      AND lat BETWEEN %s AND %s
      AND lng BETWEEN %s AND %s
      AND COALESCE(airport_code, props->>'iata', props->>'iata_code') IS NOT NULL
    LIMIT 50
    """
    try:
        _res = client.q(sql, (lat - max_radius_deg, lat + max_radius_deg,
                          lon - max_radius_deg, lon + max_radius_deg))
        candidates = _res or []
    except Exception:  # noqa: BLE001 — vertex_spatial may not have these columns
        return None
    if not candidates:
        return None
    # Pick closest by squared planar distance (good enough at this scale).
    best = None
    best_d2 = float("inf")
    for iata, alat, alon in candidates:
        if not iata or alat is None or alon is None:
            continue
        d2 = (float(alat) - lat) ** 2 + (float(alon) - lon) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best = str(iata)
    return best


def task_flight_track_compact(window_sec: int = 300) -> dict[str, Any]:
    """Compact recent state vectors into per-flight tracks."""
    run_id = _new_run_id("track")
    cutoff_ms = _now_ms() - max(60, int(window_sec)) * 1000

    # Cap the working set to avoid runaway memory; 100k points is plenty.
    sql = _SELECT_RECENT_SQL_TPL.format(limit=100_000)

    by_flight: dict[tuple[str, str], dict[str, Any]] = {}
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, (cutoff_ms,))
        for row in _res:
            icao24, callsign, lat, lon, alt, vel, ts_ms = row
            key = (str(icao24), str(callsign or ""))
            entry = by_flight.setdefault(key, {
                "icao24": icao24,
                "callsign": callsign,
                "points": [],
                "ts_min": ts_ms,
                "ts_max": ts_ms,
                "alt_max": 0.0,
                "vel_max": 0.0,
            })
            entry["points"].append((float(lat), float(lon)))
            entry["ts_min"] = min(entry["ts_min"], ts_ms)
            entry["ts_max"] = max(entry["ts_max"], ts_ms)
            if alt is not None:
                entry["alt_max"] = max(entry["alt_max"], float(alt))
            if vel is not None:
                entry["vel_max"] = max(entry["vel_max"], float(vel))

    written = 0
    if by_flight:
        if True:
            client = get_kotoba_client()
            for (icao24, callsign), entry in by_flight.items():
                points = entry["points"]
                if len(points) < 2:
                    continue
                vertex_id = f"{icao24}:{entry['ts_min']}"
                geojson = _build_linestring(points)
                # Origin = nearest airport to first point; dest = nearest to last.
                # If aircraft was high-altitude only (e.g. cruising overflight),
                # both end up near transit airports, which is acceptable noise.
                origin_iata = _nearest_airport_iata(cur, points[0][0], points[0][1])
                dest_iata = _nearest_airport_iata(cur, points[-1][0], points[-1][1])
                params = (
                    vertex_id,
                    icao24,
                    callsign or None,
                    entry["ts_min"],
                    entry["ts_max"],
                    origin_iata, dest_iata,
                    geojson,
                    entry["alt_max"],
                    entry["vel_max"],
                    len(points),
                    ACTOR_DID, "anon", 1, DEFAULT_REPO,
                    _now_iso(),
                )
                try:
                    _res = client.q(_INSERT_TRACK_SQL, params)
                    written += 1
                except Exception:  # noqa: BLE001
                    continue

    return {
        "runId": run_id,
        "tracksWritten": written,
        "flightsSeen": len(by_flight),
    }


# ──────────────────────────────────────────────────────────────────────
# Task: flight.registry.refresh — backfill vertex_aircraft from OpenSky DB
# ──────────────────────────────────────────────────────────────────────

# OpenSky publishes a complete aircraft database CSV (~620K rows, CC-BY 4.0).
# It is the most comprehensive open registry: icao24, registration, model,
# manufacturer, operator, owner, country code (registration prefix).
OPENSKY_AIRCRAFT_DB_URL = "https://opensky-network.org/datasets/metadata/aircraft-database-complete-2024-10.csv"

_INSERT_AIRCRAFT_SQL = """
INSERT INTO vertex_aircraft (
  vertex_id, label, did, rkey, repo,
  tail_number, icao24, mode_s,
  registration_country, registration_country_iso2, manufacturer, model, aircraft_type,
  operator_did, legal_owner_did, status,
  source_url, source_license, props,
  actor_did, org_did, sensitivity_ord, owner_did, created_date
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_INSERT_STATE_FOR_AIRCRAFT_EDGE_SQL = """
INSERT INTO edge_aircraft_state_for_aircraft (
  edge_id, src_vid, dst_vid, _seq, created_date,
  sensitivity_ord, owner_did, ts_ms
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

# Country prefix → ISO 3166-1 alpha-2. Source: ICAO Annex 7. Subset of the
# most common ones; rare prefixes fall back to NULL (re-resolved at query
# time if needed).
_ICAO_PREFIX_ISO2: dict[str, str] = {
    "N": "US", "C-": "CA", "G-": "GB", "F-": "FR", "D-": "DE",
    "JA": "JP", "B-": "CN", "VH": "AU", "PH": "NL", "OE": "AT",
    "OO": "BE", "EC": "ES", "I-": "IT", "EI": "IE", "OK": "CZ",
    "HB": "CH", "OY": "DK", "LX": "LU", "SP": "PL", "SX": "GR",
    "ZK": "NZ", "RA": "RU", "VT": "IN", "9V": "SG", "HL": "KR",
    "B-1": "CN", "B-2": "CN", "B-3": "CN",
    "TC": "TR", "LV": "AR", "PR": "BR", "PP": "BR", "PT": "BR",
    "XA": "MX", "ZS": "ZA", "9M": "MY", "PK": "ID", "RP": "PH",
    "HS": "TH", "VN": "VN",
}


def _icao24_to_country_iso2(reg: str) -> str | None:
    """Resolve a tail number / registration prefix to ISO 3166-1 alpha-2.

    Tries longest-prefix match against a curated table. Returns None if no
    rule matches; caller may fall back to OpenSky's `country` column or
    leave NULL.
    """
    if not reg:
        return None
    s = reg.upper().strip()
    # Longest prefix wins (e.g. "B-1" before "B-").
    for pref in sorted(_ICAO_PREFIX_ISO2.keys(), key=len, reverse=True):
        if s.startswith(pref):
            return _ICAO_PREFIX_ISO2[pref]
    return None


def task_flight_registry_refresh(csv_url: Any = None, max_rows: int = 200_000) -> dict[str, Any]:
    """Backfill vertex_aircraft from OpenSky aircraft database CSV.

    PK collision (icao24) is harmless — RW silently overwrites. Run weekly
    (R/P7D) so updated registrations propagate. max_rows caps the per-run
    ingest to amortize Hummock pressure.
    """
    run_id = _new_run_id("registry")
    url = (csv_url if isinstance(csv_url, str) and csv_url else OPENSKY_AIRCRAFT_DB_URL)

    # Stream CSV; OpenSky DB is ~30 MB plain-text.
    req = Request(url, headers={"user-agent": "etzhayyim-maps-flightradar/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=120.0) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, OSError) as exc:
        return {"runId": run_id, "aircraftIngested": 0, "skipped": 0, "error": str(exc)[:200]}

    # CSV columns vary; standard header: icao24,registration,manufacturericao,
    # manufacturername,model,typecode,serialnumber,linenumber,icaoaircrafttype,
    # operator,operatorcallsign,operatoricao,operatoriata,owner,...,country
    import csv as _csv
    import io as _io
    import sys as _sys
    # OpenSky DB has fields > Python's default 131072 byte limit (some rows
    # carry concatenated owner/operator metadata).
    _csv.field_size_limit(_sys.maxsize)
    # OpenSky aircraft DB uses APOSTROPHES (single-quote) as the quote
    # character, not standard double-quote. Without quotechar="'" every
    # cell value retains its surrounding apostrophes (e.g. 'icao24' returns
    # the 8-char string "'abcdef'" instead of "abcdef") and the length-6
    # validation drops every row.
    reader = _csv.DictReader(_io.StringIO(raw), quotechar="'")

    written = 0
    skipped = 0
    now_iso = _now_iso()
    # vertex_aircraft.created_date is DATE — use YYYY-MM-DD slice of the
    # ISO 8601 stamp.
    today_date = now_iso[:10]
    cap = max(1, min(int(max_rows), 1_000_000))

    if True:

        client = get_kotoba_client()
        for row in reader:
            if written + skipped >= cap:
                break
            icao24 = (row.get("icao24") or "").strip().lower()
            if not icao24 or len(icao24) != 6:
                skipped += 1
                continue
            tail = (row.get("registration") or "").strip()
            country = (row.get("country") or "").strip()
            iso2 = _icao24_to_country_iso2(tail)
            manufacturer = (row.get("manufacturername") or row.get("manufacturericao") or "").strip()
            model = (row.get("model") or "").strip()
            typecode = (row.get("typecode") or row.get("icaoaircrafttype") or "").strip()
            operator = (row.get("operator") or row.get("operatoricao") or row.get("operatoriata") or "").strip()
            owner = (row.get("owner") or "").strip()

            did = f"did:web:maps.etzhayyim.com:aircraft:{icao24}"
            vertex_id = f"at://{did}/com.etzhayyim.apps.maps.aircraft/{icao24}"
            operator_did = f"did:web:maps.etzhayyim.com:operator:{operator.lower().replace(' ', '_')}" if operator else None
            owner_did = f"did:web:maps.etzhayyim.com:owner:{owner.lower().replace(' ', '_')}" if owner else None

            params = (
                vertex_id,
                "Aircraft",
                did,
                icao24,
                did,
                tail or None,
                icao24,
                None,  # mode_s
                country or None,
                iso2,
                manufacturer or None,
                model or None,
                typecode or None,
                operator_did,
                owner_did,
                "active",
                url,
                "CC-BY 4.0",
                "{}",
                ACTOR_DID,
                "anon",
                1,
                DEFAULT_REPO,
                today_date,
            )
            try:
                _res = client.q(_INSERT_AIRCRAFT_SQL, params)
                written += 1
            except Exception:  # noqa: BLE001
                skipped += 1
                continue

    return {
        "runId": run_id,
        "aircraftIngested": written,
        "skipped": skipped,
        "source": url,
    }


# ──────────────────────────────────────────────────────────────────────
# Task: flight.registry.linkLive — bridge state ↔ registered aircraft
# ──────────────────────────────────────────────────────────────────────

_SELECT_UNLINKED_STATE_SQL_TPL = """
SELECT s.vertex_id, s.icao24, s.ts_ms, a.vertex_id, a.did
FROM vertex_aircraft_state s
JOIN vertex_aircraft a ON a.icao24 = s.icao24
WHERE s.aircraft_did IS NULL
LIMIT {limit}
"""

_UPDATE_STATE_AIRCRAFT_DID_SQL = """
DELETE FROM vertex_aircraft_state WHERE vertex_id = %s
"""
# RW lacks UPDATE — re-insert with the new column. We capture the row, set
# aircraft_did, and re-INSERT (PK overwrite). Skipped here for the first
# pass: linker just emits the edge, leaves aircraft_did to a follow-up
# (UPDATE-via-delete-then-insert costs more than the indexed JOIN benefit).


def task_flight_registry_link_live(max_links: int = 50_000) -> dict[str, Any]:
    """Emit edge_aircraft_state_for_aircraft for every (state, aircraft) pair
    matched by icao24.

    Idempotent on edge_id = `state_vid → aircraft_vid`. Only writes the
    edge — the typed `aircraft_did` column on vertex_aircraft_state is left
    NULL (RW UPDATE non-trivial); query-time JOIN via the edge is plenty
    fast given idx_aircraft_state_for_aircraft_src.
    """
    run_id = _new_run_id("link")
    cap = max(1, min(int(max_links), 500_000))
    sql_select = _SELECT_UNLINKED_STATE_SQL_TPL.format(limit=cap)

    written = 0
    now_iso = _now_iso()
    if True:
        client = get_kotoba_client()
        _res = client.q(sql_select)
        rows = _res or []
        for state_vid, _icao24, ts_ms, aircraft_vid, _did in rows:
            edge_id = f"{state_vid}->{aircraft_vid}"
            try:
                _res = client.q(
                    _INSERT_STATE_FOR_AIRCRAFT_EDGE_SQL,
                    (edge_id, state_vid, aircraft_vid, ts_ms, now_iso, 1, DEFAULT_REPO, ts_ms),
                )
                written += 1
            except Exception:  # noqa: BLE001
                continue

    return {"runId": run_id, "linksWritten": written}


# ──────────────────────────────────────────────────────────────────────
# LangServer registration
# ──────────────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire aircraft live primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    t("flight.live.poll", task_flight_live_poll, timeout=30_000)
    t("flight.track.compact", task_flight_track_compact, timeout=120_000)
    t("flight.registry.refresh", task_flight_registry_refresh, timeout=1_800_000)
    t("flight.registry.linkLive", task_flight_registry_link_live, timeout=600_000)


__all__ = [
    "register",
    "task_flight_live_poll",
    "task_flight_track_compact",
    "task_flight_registry_refresh",
    "task_flight_registry_link_live",
    "_opensky_state_to_row",
    "_adsbfi_aircraft_to_row",
    "_build_linestring",
]
