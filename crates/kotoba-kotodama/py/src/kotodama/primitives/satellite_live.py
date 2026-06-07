"""maps live satellite primitives — N2YO-equivalent TLE catalog + visibility passes.

ADR-0036 (worker-direct Hyperdrive) + ADR-0056 (BPMN-as-actor).

Three LangServer task types:
  satellite.tle.refresh       — fetch CelesTrak gp.php?GROUP={...}&FORMAT=tle,
                                 parse, write vertex_satellite_tle.
  satellite.pass.precompute   — for each observer cell × all active TLEs,
                                 SGP4-propagate next 24h, find AOS/LOS pairs
                                 above min elevation, write vertex_satellite_pass.
  satellite.pass.compute      — on-demand version of precompute for one
                                 arbitrary observer location.

SGP4 propagation uses the `sgp4` package (pure-Python implementation of the
SGP4/SDP4 model used by Space-Track + CelesTrak).

RisingWave constraints:
  - psycopg3 LIMIT $N forbidden in prepared statements.
  - no ON CONFLICT (PK overwrite, [[conventions]] rw-implicit-upsert).
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import json
import math
import os
import time
import urllib.request
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

DEFAULT_REPO = "did:web:maps.etzhayyim.com"
ACTOR_DID = "did:web:maps.etzhayyim.com:n2yo"

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"

DEFAULT_GROUPS = ["active", "starlink", "gnss", "stations"]

# Observer cells. Phase 1 = 12 KAMI bay centroids (mirror of
# maps_sentinel._BOOTSTRAP_AOIS). Phase 2 (2026-05-05) extends to 65 of the
# world's largest urban / port centers — coverage of the populated globe so
# satellite passes are visible from any major city without on-demand SGP4.
#
# Phase 2.2 (2026-05-05): `observer_h3` column now stores the real H3 res-5
# cell ID (15-char hex). The `name` slug is retained as fallback when h3 is
# unavailable. Client-side reverse lookup is via h3.cell_to_latlng() so the
# UI no longer needs to maintain a hardcoded mirror table.
_BOOTSTRAP_OBSERVERS: list[dict[str, Any]] = [
    # Japan bays (Phase 1, kept for sentinel parity)
    {"name": "tokyo_bay",        "lat": 35.50, "lon": 139.72},
    {"name": "osaka_bay",        "lat": 34.67, "lon": 135.25},
    {"name": "ise_bay",          "lat": 35.02, "lon": 136.87},
    {"name": "hakata_bay",       "lat": 33.62, "lon": 130.37},
    {"name": "sendai_bay",       "lat": 38.25, "lon": 141.07},
    {"name": "naha_okinawa",     "lat": 26.22, "lon": 127.75},
    {"name": "sapporo_ishikari", "lat": 43.22, "lon": 141.37},
    {"name": "niigata_port",     "lat": 37.95, "lon": 139.15},
    {"name": "hiroshima_bay",    "lat": 34.35, "lon": 132.47},
    {"name": "sendai_shiogama",  "lat": 38.35, "lon": 141.10},
    {"name": "kagoshima_bay",    "lat": 31.60, "lon": 130.67},
    {"name": "niihama_seto",     "lat": 33.97, "lon": 133.35},
    # Global megacities + major ports (Phase 2).
    {"name": "new_york",         "lat": 40.71, "lon": -74.01},
    {"name": "los_angeles",      "lat": 34.05, "lon": -118.24},
    {"name": "chicago",          "lat": 41.88, "lon": -87.63},
    {"name": "houston",          "lat": 29.76, "lon": -95.37},
    {"name": "san_francisco",    "lat": 37.77, "lon": -122.42},
    {"name": "miami",            "lat": 25.76, "lon": -80.19},
    {"name": "toronto",          "lat": 43.65, "lon": -79.38},
    {"name": "mexico_city",      "lat": 19.43, "lon": -99.13},
    {"name": "sao_paulo",        "lat": -23.55, "lon": -46.63},
    {"name": "rio_de_janeiro",   "lat": -22.91, "lon": -43.17},
    {"name": "buenos_aires",     "lat": -34.61, "lon": -58.38},
    {"name": "lima",             "lat": -12.05, "lon": -77.04},
    {"name": "bogota",           "lat": 4.71,  "lon": -74.07},
    {"name": "london",           "lat": 51.51, "lon": -0.13},
    {"name": "paris",            "lat": 48.86, "lon": 2.35},
    {"name": "madrid",           "lat": 40.42, "lon": -3.70},
    {"name": "berlin",           "lat": 52.52, "lon": 13.40},
    {"name": "rome",             "lat": 41.90, "lon": 12.50},
    {"name": "moscow",           "lat": 55.76, "lon": 37.62},
    {"name": "istanbul",         "lat": 41.01, "lon": 28.98},
    {"name": "cairo",            "lat": 30.04, "lon": 31.24},
    {"name": "lagos",            "lat": 6.52,  "lon": 3.38},
    {"name": "johannesburg",     "lat": -26.20, "lon": 28.05},
    {"name": "nairobi",          "lat": -1.29, "lon": 36.82},
    {"name": "dubai",            "lat": 25.20, "lon": 55.27},
    {"name": "riyadh",           "lat": 24.71, "lon": 46.68},
    {"name": "tehran",           "lat": 35.69, "lon": 51.39},
    {"name": "karachi",          "lat": 24.86, "lon": 67.01},
    {"name": "mumbai",           "lat": 19.08, "lon": 72.88},
    {"name": "delhi",            "lat": 28.61, "lon": 77.21},
    {"name": "bangalore",        "lat": 12.97, "lon": 77.59},
    {"name": "dhaka",            "lat": 23.81, "lon": 90.41},
    {"name": "bangkok",          "lat": 13.76, "lon": 100.50},
    {"name": "singapore",        "lat": 1.35,  "lon": 103.82},
    {"name": "jakarta",          "lat": -6.21, "lon": 106.85},
    {"name": "manila",           "lat": 14.60, "lon": 120.98},
    {"name": "ho_chi_minh",      "lat": 10.82, "lon": 106.63},
    {"name": "kuala_lumpur",     "lat": 3.14,  "lon": 101.69},
    {"name": "hong_kong",        "lat": 22.32, "lon": 114.17},
    {"name": "shanghai",         "lat": 31.23, "lon": 121.47},
    {"name": "beijing",          "lat": 39.90, "lon": 116.41},
    {"name": "shenzhen",         "lat": 22.54, "lon": 114.06},
    {"name": "guangzhou",        "lat": 23.13, "lon": 113.26},
    {"name": "seoul",            "lat": 37.57, "lon": 126.98},
    {"name": "taipei",           "lat": 25.03, "lon": 121.57},
    {"name": "sydney",           "lat": -33.87, "lon": 151.21},
    {"name": "melbourne",        "lat": -37.81, "lon": 144.96},
    {"name": "auckland",         "lat": -36.85, "lon": 174.76},
    {"name": "honolulu",         "lat": 21.31, "lon": -157.86},
    {"name": "anchorage",        "lat": 61.22, "lon": -149.90},
    {"name": "reykjavik",        "lat": 64.15, "lon": -21.94},
    {"name": "stockholm",        "lat": 59.33, "lon": 18.07},
    {"name": "helsinki",         "lat": 60.17, "lon": 24.94},
]

# ──────────────────────────────────────────────────────────────────────
# Helpers
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


def _new_run_id(prefix: str = "satellite") -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _http_get_text(url: str, *, timeout: float = 60.0) -> tuple[int, str]:
    req = Request(url, headers={"user-agent": "etzhayyim-maps-n2yo/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return getattr(resp, "status", 200), resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return e.code, ""
    except (URLError, OSError):
        return 0, ""


# ──────────────────────────────────────────────────────────────────────
# TLE parsing
# ──────────────────────────────────────────────────────────────────────

def _parse_tle_3line(text: str) -> list[dict[str, Any]]:
    """Parse a CelesTrak 3-line TLE bundle: [name, line1, line2] repeating.

    Extracts NORAD id, intl designator, epoch, mean motion, eccentricity,
    inclination from line1/line2 columns per the standard TLE spec.
    """
    out: list[dict[str, Any]] = []
    lines = [ln.strip("\r") for ln in text.splitlines() if ln.strip()]
    i = 0
    while i + 2 < len(lines):
        name = lines[i].strip()
        l1 = lines[i + 1]
        l2 = lines[i + 2]
        if not (l1.startswith("1 ") and l2.startswith("2 ")):
            i += 1
            continue
        try:
            norad_id = int(l1[2:7].strip())
            intl_designator = l1[9:17].strip()
            epoch_yy = int(l1[18:20])
            epoch_doy = float(l1[20:32])
            year = 2000 + epoch_yy if epoch_yy < 57 else 1900 + epoch_yy
            epoch_dt = _dt.datetime(year, 1, 1, tzinfo=_dt.UTC) + _dt.timedelta(days=epoch_doy - 1)
            inclination = float(l2[8:16].strip())
            ecc_raw = l2[26:33].strip()
            eccentricity = float("0." + ecc_raw) if ecc_raw else 0.0
            mean_motion = float(l2[52:63].strip())
        except (ValueError, IndexError):
            i += 3
            continue
        out.append({
            "norad_id": norad_id,
            "intl_designator": intl_designator,
            "name": name,
            "line1": l1,
            "line2": l2,
            "epoch_ms": int(epoch_dt.timestamp() * 1000),
            "mean_motion": mean_motion,
            "eccentricity": eccentricity,
            "inclination_deg": inclination,
        })
        i += 3
    return out


# ──────────────────────────────────────────────────────────────────────
# DB writers
# ──────────────────────────────────────────────────────────────────────

_INSERT_TLE_SQL = """
INSERT INTO vertex_satellite_tle (
  vertex_id, norad_id, intl_designator, name, line1, line2,
  epoch_ms, mean_motion, eccentricity, inclination_deg,
  source, catalog_group, ingested_at_ms,
  actor_did, org_did, sensitivity_ord, owner_did
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _insert_tle_rows(rows: list[dict[str, Any]], *, source: str, group: str) -> int:
    if not rows:
        return 0
    written = 0
    ingested_at_ms = _now_ms()
    if True:
        client = get_kotoba_client()
        for r in rows:
            vertex_id = f"{r['norad_id']}:{r['epoch_ms']}"
            params = (
                vertex_id,
                r["norad_id"], r["intl_designator"], r["name"],
                r["line1"], r["line2"],
                r["epoch_ms"], r["mean_motion"], r["eccentricity"], r["inclination_deg"],
                source, group, ingested_at_ms,
                ACTOR_DID, "anon", 1, DEFAULT_REPO,
            )
            try:
                _res = client.q(_INSERT_TLE_SQL, params)
                written += 1
            except Exception:  # noqa: BLE001
                continue
    return written


_INSERT_PASS_SQL = """
INSERT INTO vertex_satellite_pass (
  vertex_id, norad_id, observer_h3, observer_lat, observer_lon,
  aos_ms, los_ms, tca_ms, max_elevation_deg, peak_azimuth_deg,
  visible_at_night, magnitude, computed_at_ms,
  actor_did, org_did, sensitivity_ord, owner_did
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _insert_pass_rows(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    written = 0
    computed_at_ms = _now_ms()
    if True:
        client = get_kotoba_client()
        for r in rows:
            vertex_id = f"{r['norad_id']}:{r['observer_h3']}:{r['aos_ms']}"
            params = (
                vertex_id,
                r["norad_id"], r["observer_h3"], r["observer_lat"], r["observer_lon"],
                r["aos_ms"], r["los_ms"], r.get("tca_ms"),
                r["max_elevation_deg"], r.get("peak_azimuth_deg"),
                r.get("visible_at_night", False), r.get("magnitude"),
                computed_at_ms,
                ACTOR_DID, "anon", 1, DEFAULT_REPO,
            )
            try:
                _res = client.q(_INSERT_PASS_SQL, params)
                written += 1
            except Exception:  # noqa: BLE001
                continue
    return written


# ──────────────────────────────────────────────────────────────────────
# SGP4 propagation
# ──────────────────────────────────────────────────────────────────────

def _sgp4_satrec(line1: str, line2: str) -> Any | None:
    try:
        from sgp4.api import Satrec  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return Satrec.twoline2rv(line1, line2)
    except (ValueError, RuntimeError):
        return None


def _eci_to_topocentric(
    sat_eci_km: tuple[float, float, float],
    obs_lat_deg: float,
    obs_lon_deg: float,
    jd: float,
    fr: float,
) -> tuple[float, float]:
    """Compute (elevation_deg, azimuth_deg) of a satellite from observer.

    Uses standard ECI→ECEF→ENU rotation. obs altitude assumed 0 (sea level).
    """
    # GMST (simplified IAU 1982): theta = 280.46061837 + 360.98564736629 * (JD - 2451545.0)
    t = (jd + fr) - 2451545.0
    gmst_deg = (280.46061837 + 360.98564736629 * t) % 360.0
    gmst_rad = math.radians(gmst_deg)

    # Observer position in ECI (assume Re = 6378.137 km, sea level)
    re = 6378.137
    lat_rad = math.radians(obs_lat_deg)
    lon_rad = math.radians(obs_lon_deg)
    obs_x = re * math.cos(lat_rad) * math.cos(gmst_rad + lon_rad)
    obs_y = re * math.cos(lat_rad) * math.sin(gmst_rad + lon_rad)
    obs_z = re * math.sin(lat_rad)

    # Range vector (sat - observer) in ECI
    rx = sat_eci_km[0] - obs_x
    ry = sat_eci_km[1] - obs_y
    rz = sat_eci_km[2] - obs_z

    # Rotate to local ENU (east/north/up) at observer
    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    sin_lst = math.sin(gmst_rad + lon_rad)
    cos_lst = math.cos(gmst_rad + lon_rad)

    east = -sin_lst * rx + cos_lst * ry
    north = -sin_lat * cos_lst * rx - sin_lat * sin_lst * ry + cos_lat * rz
    up = cos_lat * cos_lst * rx + cos_lat * sin_lst * ry + sin_lat * rz

    range_km = math.sqrt(rx * rx + ry * ry + rz * rz)
    elevation_deg = math.degrees(math.asin(max(-1.0, min(1.0, up / range_km)))) if range_km > 0 else -90.0
    azimuth_deg = (math.degrees(math.atan2(east, north)) + 360.0) % 360.0
    return elevation_deg, azimuth_deg


def _datetime_to_jd_fr(dt: _dt.datetime) -> tuple[float, float]:
    """Convert UTC datetime to (jd, fr) suitable for sgp4 sgp4(jd, fr)."""
    a = (14 - dt.month) // 12
    y = dt.year + 4800 - a
    m = dt.month + 12 * a - 3
    jdn = dt.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    frac = (dt.hour - 12) / 24.0 + dt.minute / 1440.0 + (dt.second + dt.microsecond / 1_000_000) / 86400.0
    return float(jdn), frac


def _h3_cell_for(lat: float, lon: float, res: int = 5) -> str | None:
    """Resolve (lat, lon) → H3 cell ID at the requested resolution.

    Tries h3 v4 API first (`latlng_to_cell`), falls back to v3 (`geo_to_h3`),
    then to None if h3 is not installed. The fallback is the observer's name
    slug — callers should use that as `observer_h3` if this returns None.
    """
    try:
        import h3  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        if hasattr(h3, "latlng_to_cell"):
            return str(h3.latlng_to_cell(lat, lon, res))
        if hasattr(h3, "geo_to_h3"):
            return str(h3.geo_to_h3(lat, lon, res))
    except Exception:  # noqa: BLE001
        return None
    return None


def _solar_elevation_deg(obs_lat: float, obs_lon: float, dt: _dt.datetime) -> float:
    """Approximate solar elevation at observer (NOAA simplified equations).

    Negative = sun below horizon. < -6° is civil dusk → satellite reflected
    sunlight is visible to a ground observer. Used to gate `visible_at_night`.
    """
    n = (dt - _dt.datetime(2000, 1, 1, 12, 0, 0, tzinfo=_dt.UTC)).total_seconds() / 86400.0
    L = (280.460 + 0.9856474 * n) % 360.0
    g = math.radians((357.528 + 0.9856003 * n) % 360.0)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst_deg = (280.46061837 + 360.98564736629 * n) % 360.0
    lst = math.radians((gmst_deg + obs_lon) % 360.0)
    h = lst - ra
    lat_rad = math.radians(obs_lat)
    sin_alt = math.sin(lat_rad) * math.sin(dec) + math.cos(lat_rad) * math.cos(dec) * math.cos(h)
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))


def _approx_satellite_magnitude(range_km: float, elevation_deg: float) -> float:
    """Crude apparent visual magnitude estimate.

    Uses LEO-typical intrinsic magnitude (≈+1.5 at 1000 km, full phase) +
    log-distance term + simple phase angle proxy from elevation. Real values
    need solar phase angle + satellite-specific size/albedo; this is a
    sufficient ordering signal for "is this pass worth watching?".

    Returns +99 for satellites below 0° (under horizon).
    """
    if elevation_deg <= 0 or range_km <= 0:
        return 99.0
    # Distance term: each doubling of range adds ~1.5 magnitudes.
    intrinsic = 1.5
    distance_term = 5.0 * math.log10(range_km / 1000.0)
    # Phase proxy: lower elevation = higher phase angle = dimmer.
    phase_term = (90.0 - elevation_deg) * 0.015
    return intrinsic + distance_term + phase_term


def _range_km_to_sat(
    sat_eci_km: tuple[float, float, float],
    obs_lat_deg: float,
    obs_lon_deg: float,
    jd: float,
    fr: float,
) -> float:
    """Slant range observer→satellite in km."""
    t = (jd + fr) - 2451545.0
    gmst_rad = math.radians((280.46061837 + 360.98564736629 * t) % 360.0)
    re = 6378.137
    lat_rad = math.radians(obs_lat_deg)
    lon_rad = math.radians(obs_lon_deg)
    obs_x = re * math.cos(lat_rad) * math.cos(gmst_rad + lon_rad)
    obs_y = re * math.cos(lat_rad) * math.sin(gmst_rad + lon_rad)
    obs_z = re * math.sin(lat_rad)
    rx = sat_eci_km[0] - obs_x
    ry = sat_eci_km[1] - obs_y
    rz = sat_eci_km[2] - obs_z
    return math.sqrt(rx * rx + ry * ry + rz * rz)


def _find_passes(
    satrec: Any,
    obs_lat: float,
    obs_lon: float,
    start_dt: _dt.datetime,
    window_h: int,
    min_elevation_deg: float,
    step_sec: int = 60,
) -> list[dict[str, Any]]:
    """Walk SGP4 in step_sec increments; emit one row per AOS→LOS arc above min_elevation.

    For each pass, also computes:
      - magnitude  : approximate apparent visual magnitude at TCA
      - visible_at_night : true if observer was in civil dusk/night at TCA
                           (sun ≤ -6°) AND magnitude ≤ 6.0 (naked-eye limit)
    """
    out: list[dict[str, Any]] = []
    in_pass = False
    aos_ms = 0
    max_el = -90.0
    peak_az = 0.0
    tca_ms = 0
    tca_range_km = 0.0
    tca_dt = start_dt
    end_dt = start_dt + _dt.timedelta(hours=window_h)
    cur_dt = start_dt
    while cur_dt <= end_dt:
        jd, fr = _datetime_to_jd_fr(cur_dt)
        e, r, _v = satrec.sgp4(jd, fr)
        if e == 0:
            el, az = _eci_to_topocentric(r, obs_lat, obs_lon, jd, fr)
            ts_ms = int(cur_dt.timestamp() * 1000)
            if el >= min_elevation_deg and not in_pass:
                in_pass = True
                aos_ms = ts_ms
                max_el = el
                peak_az = az
                tca_ms = ts_ms
                tca_range_km = _range_km_to_sat(r, obs_lat, obs_lon, jd, fr)
                tca_dt = cur_dt
            elif in_pass and el >= min_elevation_deg:
                if el > max_el:
                    max_el = el
                    peak_az = az
                    tca_ms = ts_ms
                    tca_range_km = _range_km_to_sat(r, obs_lat, obs_lon, jd, fr)
                    tca_dt = cur_dt
            elif in_pass and el < min_elevation_deg:
                mag = _approx_satellite_magnitude(tca_range_km, max_el)
                sun_el = _solar_elevation_deg(obs_lat, obs_lon, tca_dt)
                visible = sun_el <= -6.0 and mag <= 6.0
                out.append({
                    "aos_ms": aos_ms,
                    "los_ms": ts_ms,
                    "tca_ms": tca_ms,
                    "max_elevation_deg": max_el,
                    "peak_azimuth_deg": peak_az,
                    "visible_at_night": visible,
                    "magnitude": round(mag, 2),
                })
                in_pass = False
                max_el = -90.0
        cur_dt = cur_dt + _dt.timedelta(seconds=step_sec)
    if in_pass:
        mag = _approx_satellite_magnitude(tca_range_km, max_el)
        sun_el = _solar_elevation_deg(obs_lat, obs_lon, tca_dt)
        visible = sun_el <= -6.0 and mag <= 6.0
        out.append({
            "aos_ms": aos_ms,
            "los_ms": int(end_dt.timestamp() * 1000),
            "tca_ms": tca_ms,
            "max_elevation_deg": max_el,
            "peak_azimuth_deg": peak_az,
            "visible_at_night": visible,
            "magnitude": round(mag, 2),
        })
    return out


# ──────────────────────────────────────────────────────────────────────
# Task: satellite.tle.refresh
# ──────────────────────────────────────────────────────────────────────

def task_satellite_tle_refresh(groups: Any = None) -> dict[str, Any]:
    run_id = _new_run_id("tle")
    if not groups or not isinstance(groups, list):
        env_groups = os.environ.get("SATELLITE_TLE_GROUPS_JSON", "").strip()
        if env_groups:
            try:
                parsed = json.loads(env_groups)
                groups = parsed if isinstance(parsed, list) else DEFAULT_GROUPS
            except (TypeError, ValueError):
                groups = DEFAULT_GROUPS
        else:
            groups = DEFAULT_GROUPS

    by_group: dict[str, int] = {}
    total = 0
    for g in groups:
        url = f"{CELESTRAK_GP_URL}?GROUP={g}&FORMAT=tle"
        status, text = _http_get_text(url)
        if status != 200 or not text:
            by_group[str(g)] = 0
            continue
        rows = _parse_tle_3line(text)
        written = _insert_tle_rows(rows, source="celestrak", group=str(g))
        by_group[str(g)] = written
        total += written

    return {
        "runId": run_id,
        "tleIngested": total,
        "byGroup": by_group,
    }


# ──────────────────────────────────────────────────────────────────────
# Task: satellite.pass.precompute
# ──────────────────────────────────────────────────────────────────────

_LATEST_TLE_SQL_TPL = """
SELECT norad_id, name, line1, line2 FROM vertex_satellite_tle
WHERE catalog_group = %s
  AND vertex_id IN (
    SELECT vertex_id FROM (
      SELECT vertex_id, norad_id, ROW_NUMBER() OVER (PARTITION BY norad_id ORDER BY epoch_ms DESC) AS rn
      FROM vertex_satellite_tle
      WHERE catalog_group = %s
    ) t WHERE rn = 1
  )
LIMIT {limit}
"""


def _resolve_observers(override: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if override and isinstance(override, list):
        out: list[dict[str, Any]] = []
        for o in override:
            if not isinstance(o, dict):
                continue
            try:
                out.append({
                    "name": str(o.get("name") or f"obs-{len(out)}"),
                    "lat": float(o["lat"]),
                    "lon": float(o["lon"]),
                })
            except (KeyError, TypeError, ValueError):
                continue
        if out:
            return out
    env_val = os.environ.get("SATELLITE_OBSERVER_CELLS_JSON", "").strip()
    if env_val:
        try:
            parsed = json.loads(env_val)
            if isinstance(parsed, list):
                return _resolve_observers(parsed)
        except (TypeError, ValueError):
            pass
    return list(_BOOTSTRAP_OBSERVERS)


def task_satellite_pass_precompute(
    observers: Any = None,
    window_h: int = 24,
    min_elevation_deg: float = 10.0,
    catalog_group: str = "active",
) -> dict[str, Any]:
    run_id = _new_run_id("pass")
    obs_list = _resolve_observers(observers if isinstance(observers, list) else None)

    sql = _LATEST_TLE_SQL_TPL.format(limit=10_000)
    tles: list[tuple[int, str, str, str]] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, (catalog_group, catalog_group))
        for norad_id, name, line1, line2 in _res:
            tles.append((int(norad_id), str(name or ""), str(line1), str(line2)))

    if not tles:
        return {"runId": run_id, "passesWritten": 0, "observersCovered": 0, "tleCount": 0}

    start_dt = _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0)
    rows: list[dict[str, Any]] = []
    for obs in obs_list:
        for norad_id, _name, line1, line2 in tles:
            satrec = _sgp4_satrec(line1, line2)
            if satrec is None:
                continue
            arcs = _find_passes(
                satrec, obs["lat"], obs["lon"], start_dt, int(window_h), float(min_elevation_deg)
            )
            # Resolve real H3 res-5 cell for this observer; fall back to slug.
            obs_h3 = _h3_cell_for(obs["lat"], obs["lon"], res=5) or obs["name"]
            for arc in arcs:
                rows.append({
                    "norad_id": norad_id,
                    "observer_h3": obs_h3,
                    "observer_lat": obs["lat"],
                    "observer_lon": obs["lon"],
                    **arc,
                })

    written = _insert_pass_rows(rows)
    return {
        "runId": run_id,
        "passesWritten": written,
        "observersCovered": len(obs_list),
        "tleCount": len(tles),
    }


# ──────────────────────────────────────────────────────────────────────
# Task: satellite.pass.compute (on-demand single observer)
# ──────────────────────────────────────────────────────────────────────

def task_satellite_pass_compute(
    lat: float,
    lon: float,
    window_h: int = 24,
    min_elevation_deg: float = 10.0,
    norad_ids: Any = None,
    catalog_group: str = "active",
) -> dict[str, Any]:
    run_id = _new_run_id("pass-od")

    if norad_ids and isinstance(norad_ids, list):
        norad_clause = "AND norad_id IN (" + ",".join(str(int(x)) for x in norad_ids) + ")"
        sql = (
            "SELECT norad_id, name, line1, line2 FROM vertex_satellite_tle "
            f"WHERE catalog_group = %s {norad_clause} "
            "AND vertex_id IN ("
            "  SELECT vertex_id FROM ("
            "    SELECT vertex_id, norad_id, ROW_NUMBER() OVER (PARTITION BY norad_id ORDER BY epoch_ms DESC) AS rn"
            "    FROM vertex_satellite_tle WHERE catalog_group = %s"
            "  ) t WHERE rn = 1) "
            "LIMIT 5000"
        )
    else:
        sql = _LATEST_TLE_SQL_TPL.format(limit=2_000)

    tles: list[tuple[int, str, str, str]] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, (catalog_group, catalog_group))
        for norad_id, name, line1, line2 in _res:
            tles.append((int(norad_id), str(name or ""), str(line1), str(line2)))

    start_dt = _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0)
    passes: list[dict[str, Any]] = []
    for norad_id, name, line1, line2 in tles:
        satrec = _sgp4_satrec(line1, line2)
        if satrec is None:
            continue
        arcs = _find_passes(satrec, float(lat), float(lon), start_dt, int(window_h), float(min_elevation_deg))
        for arc in arcs:
            passes.append({"noradId": norad_id, "name": name, **arc})

    return {
        "runId": run_id,
        "passes": passes,
        "count": len(passes),
        "computedAtMs": _now_ms(),
        "fromCache": False,
    }


# ──────────────────────────────────────────────────────────────────────
# LangServer registration
# ──────────────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire satellite live primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    t("satellite.tle.refresh", task_satellite_tle_refresh, timeout=300_000)
    t("satellite.pass.precompute", task_satellite_pass_precompute, timeout=600_000)
    t("satellite.pass.compute", task_satellite_pass_compute, timeout=120_000)


__all__ = [
    "register",
    "task_satellite_tle_refresh",
    "task_satellite_pass_precompute",
    "task_satellite_pass_compute",
    "_parse_tle_3line",
    "_eci_to_topocentric",
    "_find_passes",
]
