"""maps Sentinel L7/L8 primitives — Sentinel-1/2 STAC ingest + RunPod GPU analysis.
ADR-2604271800. Phase 2: writes to typed tables vertex_satellite_scene /
vertex_satellite_analysis via sync_cursor.

Two LangServer task types:
  maps.sentinel.stac.search    — STAC POST /search across AOIs + platforms.
  maps.sentinel.runpod.analyze — RunPod Serverless sync-poll GPU analysis.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import hashlib
import json
import os
import time
import urllib.request
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

DEFAULT_REPO = "did:web:maps.etzhayyim.com"
COLLECTION_SCENE = "com.etzhayyim.apps.maps.satelliteScene"
COLLECTION_ANALYSIS = "com.etzhayyim.apps.maps.satelliteAnalysis"

ELEMENT84_STAC = "https://earth-search.aws.element84.com/v1/search"
COPERNICUS_STAC = "https://catalogue.dataspace.copernicus.eu/stac/search"

_PLATFORM_S2 = "sentinel-2-l2a"
_PLATFORM_S1 = "sentinel-1-grd"

# RunPod model registry (snake_case analysis type keys).
_ANALYSIS_MODELS: dict[str, str] = {
    "change_detection": "sentinel2_change_siamese",
    "land_use": "sentinel2_landuse_unet",
    "sar_flood": "sentinel1_flood_unet",
}
_VALID_ANALYSIS_TYPES = set(_ANALYSIS_MODELS.keys())

# Patchable poll ceiling for tests.
_RUNPOD_MAX_POLLS: int = 60

_RUNPOD_RUN_URL_TPL = "https://api.runpod.ai/v2/{endpoint}/run"
_RUNPOD_STATUS_URL_TPL = "https://api.runpod.ai/v2/{endpoint}/status/{job_id}"

# 12 KAMI-layer coordinator centroids. Used when SENTINEL_AOIS_JSON is unset.
_BOOTSTRAP_AOIS: list[dict[str, Any]] = [
    {"name": "tokyo_bay",       "bbox": [139.50, 35.30, 139.95, 35.70]},
    {"name": "osaka_bay",       "bbox": [135.00, 34.50, 135.50, 34.85]},
    {"name": "ise_bay",         "bbox": [136.65, 34.85, 137.10, 35.20]},
    {"name": "hakata_bay",      "bbox": [130.20, 33.50, 130.55, 33.75]},
    {"name": "sendai_bay",      "bbox": [140.85, 38.10, 141.30, 38.40]},
    {"name": "naha_okinawa",    "bbox": [127.55, 26.05, 127.95, 26.40]},
    {"name": "sapporo_ishikari","bbox": [141.20, 43.05, 141.55, 43.40]},
    {"name": "niigata_port",    "bbox": [139.00, 37.85, 139.30, 38.05]},
    {"name": "hiroshima_bay",   "bbox": [132.30, 34.20, 132.65, 34.50]},
    {"name": "sendai_shiogama", "bbox": [141.00, 38.25, 141.20, 38.45]},
    {"name": "kagoshima_bay",   "bbox": [130.55, 31.45, 130.80, 31.75]},
    {"name": "niihama_seto",    "bbox": [133.20, 33.85, 133.50, 34.10]},
]


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


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_rkey(prefix: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    import uuid
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _build_datetime_range(time_range_days: int) -> str:
    end = _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0)
    start = end - _dt.timedelta(days=max(1, min(int(time_range_days or 1), 365)))
    return f"{start.isoformat().replace('+00:00','Z')}/{end.isoformat().replace('+00:00','Z')}"


# ──────────────────────────────────────────────────────────────────────
# AOI helpers
# ──────────────────────────────────────────────────────────────────────

def _parse_aoi(spec: Any) -> dict[str, Any]:
    """Parse one AOI spec dict into {name, bbox: [minLon, minLat, maxLon, maxLat]}.

    Raises ValueError with a message containing 'dict', 'bbox', 'longitude',
    or 'latitude' depending on the failure so tests can assert on message content."""
    if not isinstance(spec, dict):
        raise ValueError(f"AOI spec must be a dict, got {type(spec).__name__}")
    raw_bbox = spec.get("bbox")
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        raise ValueError(f"AOI bbox must be a list of 4 numbers, got {raw_bbox!r}")
    try:
        bbox = [float(v) for v in raw_bbox]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"AOI bbox values must be numeric: {exc}") from exc
    if bbox[0] >= bbox[2]:
        raise ValueError(f"AOI longitude: minLon ({bbox[0]}) must be < maxLon ({bbox[2]})")
    if bbox[1] >= bbox[3]:
        raise ValueError(f"AOI latitude: minLat ({bbox[1]}) must be < maxLat ({bbox[3]})")
    return {"name": str(spec.get("name") or ""), "bbox": bbox}


def _resolve_aois(override: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return list of validated AOI dicts.

    Priority: override > SENTINEL_AOIS_JSON env > bootstrap."""
    if override is not None:
        raw = override
    else:
        env_val = os.environ.get("SENTINEL_AOIS_JSON", "").strip()
        if env_val:
            try:
                raw = json.loads(env_val)
            except (TypeError, ValueError):
                raw = []
        else:
            return list(_BOOTSTRAP_AOIS)

    result: list[dict[str, Any]] = []
    for item in raw:
        try:
            result.append(_parse_aoi(item))
        except ValueError:
            pass
    return result


# ──────────────────────────────────────────────────────────────────────
# HTTP helpers
# ──────────────────────────────────────────────────────────────────────

def _http_post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any] | None, str]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    h = {"content-type": "application/json", "accept": "application/json"}
    if headers:
        h.update(headers)
    req = Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status_code = getattr(resp, "status", 200)
            try:
                return status_code, json.loads(raw), raw
            except (TypeError, ValueError):
                return status_code, None, raw
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        return e.code, None, raw
    except (URLError, OSError) as e:
        return 0, None, f"urlerror: {e}"


# ──────────────────────────────────────────────────────────────────────
# STAC search
# ──────────────────────────────────────────────────────────────────────

def _stac_search(
    endpoint: str,
    collection: str,
    bbox: list[float],
    *,
    max_cloud_cover: float = 30.0,
    datetime_range: str | None = None,
    limit: int = 10,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "collections": [collection],
        "bbox": bbox,
        "datetime": datetime_range or _build_datetime_range(1),
        "limit": max(1, min(limit, 100)),
    }
    if max_cloud_cover < 100:
        payload["query"] = {"eo:cloud_cover": {"lte": max_cloud_cover}}
    status, body, _raw = _http_post_json(endpoint, payload, headers=headers, timeout=timeout)
    if status != 200 or not isinstance(body, dict):
        return []
    feats = body.get("features")
    if not isinstance(feats, list):
        return []
    return [f for f in feats if isinstance(f, dict)]


def _scene_row_from_stac(
    feature: dict[str, Any],
    *,
    platform: str = "",
) -> dict[str, Any]:
    """Map a STAC Item feature to a typed satellite scene row.

    rkey is deterministic (sha256 of scene id) so idempotent re-ingest
    produces the same vertex_id."""
    props = feature.get("properties") or {}
    feat_id = str(feature.get("id") or "")

    # Stable rkey from scene identity.
    rkey = hashlib.sha256(feat_id.encode("utf-8")).hexdigest()[:16]
    uri = f"at://{DEFAULT_REPO}/{COLLECTION_SCENE}/{rkey}"

    # Platform resolution: explicit arg > properties.platform > properties.constellation.
    resolved_platform = (
        platform
        or str(props.get("platform") or "")
        or str(props.get("constellation") or "")
    )

    # stacSelfUrl from links[rel=self].
    stac_self_url = ""
    for link in (feature.get("links") or []):
        if isinstance(link, dict) and link.get("rel") == "self":
            stac_self_url = str(link.get("href") or "")
            break

    record = {
        "$type": COLLECTION_SCENE,
        "sceneId": feat_id,
        "platform": resolved_platform,
        "datetime": str(props.get("datetime") or ""),
        "cloudCover": props.get("eo:cloud_cover"),
        "bbox": feature.get("bbox") or [],
        "stacSelfUrl": stac_self_url,
        "stacItem": feature,
        "createdAt": _now_iso(),
    }
    value_json = json.dumps(record, separators=(",", ":"), ensure_ascii=False)

    ts_ms = _now_ms()
    dt_str = str(props.get("datetime") or "")
    if dt_str:
        try:
            ts_ms = int(
                _dt.datetime.fromisoformat(dt_str.replace("Z", "+00:00")).timestamp()
                * 1000
            )
        except (TypeError, ValueError):
            pass

    now = _now_iso()
    return {
        "vertex_id": uri,
        "uri": uri,
        "cid": rkey,
        "collection": COLLECTION_SCENE,
        "rkey": rkey,
        "repo": DEFAULT_REPO,
        "repo_rev": rkey,
        "value_json": value_json,
        "indexed_at": now,
        "takedown_ref": None,
        "ts_ms": ts_ms,
        "created_at": now,
        "sensitivity_ord": 1,
        "org_id": DEFAULT_REPO,
        "user_id": DEFAULT_REPO,
        "actor_id": "sys.maps.sentinel",
    }


# ──────────────────────────────────────────────────────────────────────
# LangChain stage functions (module-level for testability)
# ──────────────────────────────────────────────────────────────────────

def _stage1_build_input(inputs: dict[str, Any]) -> dict[str, Any]:
    """Normalise analysis_type; unknown types fall back to change_detection."""
    result = dict(inputs)
    atype = str(inputs.get("analysis_type") or "")
    if atype not in _VALID_ANALYSIS_TYPES:
        result["analysis_type"] = "change_detection"
    return result


def _stage3_parse_output(output: dict[str, Any]) -> dict[str, Any]:
    """Clamp confidence to [0,1]; cap phase1 models at 0.85; add ok=True."""
    result = dict(output)
    try:
        confidence = float(output.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    model_version = str(output.get("model_version") or "")
    if model_version == "phase1":
        confidence = min(confidence, 0.85)
    result["confidence"] = confidence
    if "summary" not in result:
        result["summary"] = ""
    result["ok"] = True
    return result


# ──────────────────────────────────────────────────────────────────────
# RunPod invoke
# ──────────────────────────────────────────────────────────────────────

def _runpod_invoke_sync(
    analysis_type: str,
    scene_uri: str,
    *,
    api_key: str,
    endpoint_id: str,
    timeout_sec: int = 300,
) -> dict[str, Any]:
    """POST /run + poll /status up to _RUNPOD_MAX_POLLS times.

    Returns dict on success or when credentials are absent (ok=False).
    Raises RuntimeError on terminal job failure, TimeoutError on poll exhaustion."""
    if not api_key or not endpoint_id:
        return {
            "ok": False,
            "reason": "RUNPOD_ENDPOINT_ID_MAPS / RUNPOD_KEY not configured",
            "confidence": 0.0,
            "summary": "",
            "analysisType": analysis_type,
        }

    model_input = {
        "model": _ANALYSIS_MODELS.get(analysis_type, analysis_type),
        "analysisType": analysis_type,
        "sceneUri": scene_uri,
    }

    headers = {"authorization": f"Bearer {api_key}"}
    status, body, raw = _http_post_json(
        _RUNPOD_RUN_URL_TPL.format(endpoint=endpoint_id),
        {"input": model_input},
        headers=headers,
        timeout=30.0,
    )
    if status != 200 or not isinstance(body, dict) or not body.get("id"):
        raise RuntimeError(f"runpod /run status={status} body={raw[:200]}")
    job_id = str(body["id"])

    for _ in range(_RUNPOD_MAX_POLLS):
        try:
            req = Request(
                _RUNPOD_STATUS_URL_TPL.format(endpoint=endpoint_id, job_id=job_id),
                headers={"authorization": f"Bearer {api_key}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise RuntimeError(f"runpod /status raised: {exc}") from exc

        st = str(payload.get("status") or "")
        if st == "COMPLETED":
            out = payload.get("output") or {}
            return {
                "ok": True,
                "summary": str(out.get("summary") or ""),
                "confidence": float(out.get("confidence") or 0.0),
                "analysisType": analysis_type,
                "jobId": job_id,
            }
        if st in ("FAILED", "CANCELLED", "TIMED_OUT"):
            error_msg = str(payload.get("error") or st)
            raise RuntimeError(f"{st}: {error_msg}")
        time.sleep(1.5)

    raise TimeoutError(f"runpod poll exceeded {_RUNPOD_MAX_POLLS} polls for job {job_id}")


# ──────────────────────────────────────────────────────────────────────
# LangServer task handlers
# ──────────────────────────────────────────────────────────────────────

def task_maps_sentinel_stac_search(
    aois: list[dict[str, Any]] | None = None,
    platforms: list[str] | None = None,
    max_scenes_per_aoi: int = 10,
    time_range_days: int = 1,
    max_cloud_cover: float = 30.0,
) -> dict[str, Any]:
    """STAC search across configured platforms × AOIs.

    Writes each scene row directly to vertex_satellite_scene via sync_cursor.
    Returns summary counts for BPMN ioMapping."""
    run_id = _new_rkey("sentinel-ingest")
    resolved_aois = _resolve_aois(aois)

    if not resolved_aois:
        return {
            "runId": run_id,
            "rows": [],
            "scenesFound": 0,
            "scenesIngested": 0,
            "byPlatform": {},
        }

    platform_filter = (
        {str(p).lower() for p in platforms}
        if platforms
        else {_PLATFORM_S2, _PLATFORM_S1}
    )
    dt_range = _build_datetime_range(int(time_range_days or 1))
    cap = max(1, min(int(max_scenes_per_aoi or 10), 200))

    rows: list[dict[str, Any]] = []
    scanned = 0
    by_platform: dict[str, int] = {}

    if _PLATFORM_S2 in platform_filter:
        for aoi in resolved_aois:
            feats = _stac_search(
                ELEMENT84_STAC,
                _PLATFORM_S2,
                aoi["bbox"],
                max_cloud_cover=float(max_cloud_cover or 30),
                datetime_range=dt_range,
                limit=cap,
            )
            scanned += len(feats)
            for f in feats:
                rows.append(_scene_row_from_stac(f, platform=_PLATFORM_S2))
            by_platform[_PLATFORM_S2] = by_platform.get(_PLATFORM_S2, 0) + len(feats)

    if _PLATFORM_S1 in platform_filter:
        token = os.environ.get("COPERNICUS_OAUTH_TOKEN", "").strip()
        s1_headers = {"authorization": f"Bearer {token}"} if token else None
        for aoi in resolved_aois:
            feats = _stac_search(
                COPERNICUS_STAC,
                "SENTINEL-1",
                aoi["bbox"],
                max_cloud_cover=100.0,
                datetime_range=dt_range,
                limit=cap,
                headers=s1_headers,
            )
            scanned += len(feats)
            for f in feats:
                rows.append(_scene_row_from_stac(f, platform=_PLATFORM_S1))
            by_platform[_PLATFORM_S1] = by_platform.get(_PLATFORM_S1, 0) + len(feats)

    scenes_ingested = 0
    if rows:
        _insert_sql = (
            "INSERT INTO vertex_satellite_scene "
            "(vertex_id, repo, scene_id, platform, date_time, cloud_cover, "
            " stac_collection_id, stac_self_url, bbox, created_at, "
            " sensitivity_ord, source_did, org_id, user_id, actor_id) "
            "SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s "
            "WHERE NOT EXISTS "
            "(SELECT 1 FROM vertex_satellite_scene WHERE vertex_id = %s)"
        )
        if True:
            client = get_kotoba_client()
            for row in rows:
                record = json.loads(row["value_json"])
                bbox_json = json.dumps(
                    record.get("bbox") or [], separators=(",", ":")
                )
                params = (
                    row["vertex_id"],
                    row["repo"],
                    record.get("sceneId", ""),
                    record.get("platform", ""),
                    record.get("datetime", ""),
                    record.get("cloudCover"),
                    row["collection"],
                    record.get("stacSelfUrl", ""),
                    bbox_json,
                    row["created_at"],
                    row["sensitivity_ord"],
                    row["org_id"],
                    row["org_id"],
                    row["user_id"],
                    row["actor_id"],
                    row["vertex_id"],
                )
                _res = client.q(_insert_sql, params)
                scenes_ingested += 1

    return {
        "runId": run_id,
        "rows": rows,
        "scenesFound": scanned,
        "scenesIngested": scenes_ingested,
        "byPlatform": by_platform,
    }


def task_maps_sentinel_runpod_analyze(
    scene_uri: str = "",
    analysis_type: str = "",
    *,
    model_version: str = "",
    baseline_uri: str = "",
) -> dict[str, Any]:
    """RunPod Serverless GPU analysis for one satellite scene.

    Always writes a vertex_satellite_analysis row (degraded on failure).
    Returns result dict for BPMN ioMapping."""
    if not scene_uri:
        return {
            "ok": False,
            "summary": "(missing scene_uri)",
            "confidence": 0.0,
            "analysisUri": "",
            "analysisType": analysis_type,
            "modelVersion": model_version,
        }

    stage1 = _stage1_build_input({
        "scene_uri": scene_uri,
        "analysis_type": analysis_type,
        "api_key": os.environ.get("RUNPOD_KEY", "").strip(),
        "endpoint_id": os.environ.get("RUNPOD_ENDPOINT_ID_MAPS", "").strip(),
    })
    normalized_type = stage1["analysis_type"]
    api_key = stage1["api_key"]
    endpoint_id = stage1["endpoint_id"]

    ok = False
    summary = ""
    confidence = 0.0

    try:
        rp = _runpod_invoke_sync(
            normalized_type,
            scene_uri,
            api_key=api_key,
            endpoint_id=endpoint_id,
            timeout_sec=int(os.environ.get("RUNPOD_TIMEOUT_SEC", "300") or "300"),
        )
        if rp.get("ok"):
            stage3 = _stage3_parse_output({
                "confidence": rp.get("confidence", 0.0),
                "model_version": model_version or "unknown",
                "summary": rp.get("summary", ""),
            })
            ok = True
            confidence = stage3["confidence"]
            summary = str(stage3.get("summary") or "")
        else:
            ok = False
            confidence = float(rp.get("confidence") or 0.0)
            summary = str(rp.get("reason") or rp.get("summary") or "")
    except (RuntimeError, TimeoutError) as exc:
        ok = False
        summary = f"({exc})"
        confidence = 0.0

    rkey = _new_rkey("ana")
    analysis_uri = f"at://{DEFAULT_REPO}/{COLLECTION_ANALYSIS}/{rkey}"
    record = {
        "$type": COLLECTION_ANALYSIS,
        "sceneUri": scene_uri,
        "analysisType": normalized_type,
        "summary": summary,
        "confidence": confidence,
        "modelVersion": model_version or "unknown",
        "createdAt": _now_iso(),
    }
    value_json = json.dumps(record, separators=(",", ":"), ensure_ascii=False)

    _insert_sql = (
        "INSERT INTO vertex_satellite_analysis "
        "(vertex_id, repo, scene_uri, analysis_type, model_version, value_json, "
        " summary, confidence, ok, created_at, sensitivity_ord, source_did, "
        " org_id, user_id, actor_id) "
        "SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s "
        "WHERE NOT EXISTS "
        "(SELECT 1 FROM vertex_satellite_analysis WHERE vertex_id = %s)"
    )
    params = (
        analysis_uri,
        DEFAULT_REPO,
        scene_uri,
        normalized_type,
        model_version or "unknown",
        value_json,       # index 5
        summary,
        confidence,
        ok,
        _now_iso(),
        1,
        DEFAULT_REPO,
        DEFAULT_REPO,
        DEFAULT_REPO,
        "sys.maps.sentinel",
        analysis_uri,
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(_insert_sql, params)

    return {
        "ok": ok,
        "summary": summary,
        "confidence": confidence,
        "analysisUri": analysis_uri,
        "analysisType": normalized_type,
        "modelVersion": model_version or "unknown",
    }


# ──────────────────────────────────────────────────────────────────────
# LangServer registration
# ──────────────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire maps Sentinel primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    t("maps.sentinel.stac.search", task_maps_sentinel_stac_search,
      timeout=max(timeout_ms, 180_000))
    t("maps.sentinel.runpod.analyze", task_maps_sentinel_runpod_analyze,
      timeout=max(timeout_ms, 600_000))


__all__ = [
    "register",
    "task_maps_sentinel_stac_search",
    "task_maps_sentinel_runpod_analyze",
    "_parse_aoi",
    "_resolve_aois",
    "_stac_search",
    "_scene_row_from_stac",
    "_runpod_invoke_sync",
    "_stage1_build_input",
    "_stage3_parse_output",
    "_RUNPOD_MAX_POLLS",
    "DEFAULT_REPO",
    "ELEMENT84_STAC",
    "COPERNICUS_STAC",
]
