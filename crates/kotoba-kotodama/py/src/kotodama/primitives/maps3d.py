"""maps3d photogrammetry pipeline primitives — 7 Zeebe task types.

Pipeline order (processTile.bpmn):
  fetchMapillary → curateImages → colmapTile
    success → simplifyAndExport → visionAnnotate → linkActor
    failure → replanReconstruction → (retry/requestMore/downgradeOsm/abort)

ADR-0056 BPMN-as-actor.

Env vars:
  MAPILLARY_TOKEN           Mapillary API v4 access token
  COLMAP_WORKER_URL         e.g. http://colmap-worker.mitama-udf.svc.cluster.local:8030
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from kotodama import llm as _llm

# ──────────────────────────────────────────────────────────────────────
# Env vars
# ──────────────────────────────────────────────────────────────────────

_MAPILLARY_TOKEN = os.environ.get("MAPILLARY_TOKEN", "").strip()
_MAPILLARY_BASE = "https://graph.mapillary.com"

_COLMAP_WORKER_URL = os.environ.get(
    "COLMAP_WORKER_URL",
    "http://colmap-worker.mitama-udf.svc.cluster.local:8030",
).rstrip("/")

_COLMAP_POLL_INTERVAL_SEC = 15
_COLMAP_MAX_POLLS = 240  # 60 min at 15s intervals

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _http_get(url: str, headers: dict[str, str] | None = None, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} GET {url}: {body}") from e


def _http_post(url: str, payload: dict, headers: dict[str, str] | None = None, timeout: float = 30.0) -> dict:
    body = json.dumps(payload).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} POST {url}: {body_text}") from e


def _h3_to_bbox(tile_h3: str) -> tuple[float, float, float, float]:
    """Convert H3 index to (west, south, east, north) bounding box.

    Uses the h3 library when available; falls back to a ~1km padding around
    the cell centre decoded from the H3 bit pattern for common resolutions.
    """
    try:
        import h3  # type: ignore[import-untyped]
        if hasattr(h3, "cell_to_boundary"):
            verts = h3.cell_to_boundary(tile_h3)  # h3-py v4: [(lat, lng), ...]
        else:
            verts = h3.h3_to_geo_boundary(tile_h3)  # h3-py v3: [(lat, lng), ...]
        lats = [v[0] for v in verts]
        lngs = [v[1] for v in verts]
        return min(lngs), min(lats), max(lngs), max(lats)
    except ImportError:
        pass

    # Approximate fallback: decode centre from H3 index integer.
    # Works for resolutions 7-12 (city-block to building scale).
    try:
        idx = int(tile_h3, 16) if len(tile_h3) <= 16 else int(tile_h3)
    except (ValueError, TypeError):
        return 139.6, 35.5, 139.8, 35.7  # default Tokyo centre

    # H3 resolution 0-15 encoded in bits 52-55 of the 64-bit index.
    res = (idx >> 52) & 0xF
    # Approximate cell edge length in degrees (rough: res11 ≈ 0.00022°)
    deg_pad = 0.00022 * (4 ** (11 - min(res, 11))) * 2
    # Extract rough lat/lng from the base cell + digits. This is a gross
    # approximation; replace with h3-py for production accuracy.
    lat_raw = ((idx >> 4) & 0xFFFFFF) / 0xFFFFFF * 180.0 - 90.0
    lng_raw = ((idx >> 28) & 0xFFFFFF) / 0xFFFFFF * 360.0 - 180.0
    return lng_raw - deg_pad, lat_raw - deg_pad, lng_raw + deg_pad, lat_raw + deg_pad


# ──────────────────────────────────────────────────────────────────────
# Datom-log persistence (ADR-2605262130 / 2605312345: the kotoba Datom log
# is first-class canonical state — Datomic-isomorphic EAVT, no RisingWave).
#
# processTile.bpmn's "mark tile done" step documents that "the worker tasks
# have already INSERT-ed into vertex_spatial / vertex_vision_result / edge_*".
# These helpers make that contract true: visionAnnotate lands its detections
# in vertex_vision_result and linkActor lands its edges in
# edge_maps3d_actor_link, both via the kotoba Datomic client's upsert surface
# (:db.unique/identity on vertex_id → re-transact is idempotent).
# ──────────────────────────────────────────────────────────────────────

DEFAULT_REPO = "did:web:maps.etzhayyim.com"
COLLECTION_VISION = "com.etzhayyim.apps.maps3d.visionResult"
COLLECTION_ACTOR_LINK = "com.etzhayyim.apps.maps3d.actorLink"


def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=_dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_rkey(*parts: str) -> str:
    """Deterministic rkey so re-running a tile upserts instead of duplicating."""
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def _persist_vision_results(tile_h3: str, detections: list[dict]) -> int:
    """Upsert vision detections into vertex_vision_result. Returns rows written.

    Fail-open (matches the maps actor's kotoba-first/fail-open posture): a
    substrate outage logs nothing-special and returns the count written so far
    rather than failing the pipeline task.
    """
    if not tile_h3 or not detections:
        return 0
    client = get_kotoba_client()
    now = _now_iso()
    written = 0
    for det in detections:
        label = str(det.get("label") or "").strip()
        if not label:
            continue
        image_ref = str(det.get("imageRef") or "")
        rkey = _stable_rkey(tile_h3, label, image_ref)
        row = {
            "vertex_id": f"at://{DEFAULT_REPO}/{COLLECTION_VISION}/{rkey}",
            "tile_h3": tile_h3,
            "label": label,
            "confidence": float(det.get("confidence") or 0),
            "category": str(det.get("category") or "building"),
            "image_ref": image_ref,
            "source": "murakumo-vision",
            "ingest_at": now,
            "owner_did": DEFAULT_REPO,
        }
        try:
            client.insert_row("vertex_vision_result", row)
            written += 1
        except Exception:
            break  # substrate unavailable — fail-open, keep what landed
    return written


def _persist_actor_links(tile_h3: str, links: list[dict]) -> int:
    """Upsert resolved actor links into edge_maps3d_actor_link. Returns rows written."""
    if not tile_h3 or not links:
        return 0
    client = get_kotoba_client()
    now = _now_iso()
    written = 0
    for lk in links:
        actor_did = str(lk.get("actorDid") or "")
        if not actor_did:
            continue
        label = str(lk.get("label") or lk.get("detectionId") or "")
        rkey = _stable_rkey(tile_h3, label, actor_did)
        row = {
            "vertex_id": f"at://{DEFAULT_REPO}/{COLLECTION_ACTOR_LINK}/{rkey}",
            "tile_h3": tile_h3,
            "label": label,
            "actor_did": actor_did,
            "confidence": float(lk.get("confidence") or 0),
            "source": str(lk.get("source") or "llm-disambiguate"),
            "ingest_at": now,
            "owner_did": DEFAULT_REPO,
        }
        try:
            client.insert_row("edge_maps3d_actor_link", row)
            written += 1
        except Exception:
            break  # fail-open
    return written


# ──────────────────────────────────────────────────────────────────────
# Task 7 (pipeline step 3 — fetched first in reverse topo): fetchMapillary
# ──────────────────────────────────────────────────────────────────────

async def task_maps3d_fetch_mapillary(
    tileH3: str = "",
    maxImages: int = 200,
    minQuality: float = 0.5,
) -> dict:
    """Fetch Mapillary v4 street-level image candidates for a tile.

    Returns candidates (list of image metadata objects) + totalAvailable.
    Requires MAPILLARY_TOKEN env var.
    """
    if not tileH3:
        return {"ok": False, "candidates": [], "totalAvailable": 0, "error": "tileH3 required"}
    if not _MAPILLARY_TOKEN:
        return {"ok": False, "candidates": [], "totalAvailable": 0, "error": "MAPILLARY_TOKEN not set"}

    west, south, east, north = _h3_to_bbox(tileH3)
    bbox_str = f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}"
    fields = "id,thumb_1024_url,computed_geometry,quality_score,captured_at,creator,compass_angle"
    url = (
        f"{_MAPILLARY_BASE}/images"
        f"?access_token={_MAPILLARY_TOKEN}"
        f"&fields={fields}"
        f"&bbox={bbox_str}"
        f"&limit={min(maxImages, 2000)}"
    )

    try:
        data = _http_get(url, timeout=60.0)
    except RuntimeError as e:
        return {"ok": False, "candidates": [], "totalAvailable": 0, "error": str(e)}

    images = data.get("data", [])
    candidates = [
        {
            "id": img.get("id", ""),
            "thumbUrl": img.get("thumb_1024_url", ""),
            "lng": (img.get("computed_geometry") or {}).get("coordinates", [0, 0])[0],
            "lat": (img.get("computed_geometry") or {}).get("coordinates", [0, 0])[1],
            "qualityScore": float(img.get("quality_score") or 0),
            "capturedAt": img.get("captured_at", ""),
            "compassAngle": float(img.get("compass_angle") or 0),
        }
        for img in images
        if float(img.get("quality_score") or 0) >= minQuality
    ]

    return {
        "ok": True,
        "candidates": candidates,
        "totalAvailable": len(candidates),
        "bbox": {"west": west, "south": south, "east": east, "north": north},
    }


# ──────────────────────────────────────────────────────────────────────
# Task 6 (step 4): curateImages — LLM-based 30-image down-select
# ──────────────────────────────────────────────────────────────────────

_CURATE_SYSTEM = (
    "You select street-level images for 3D photogrammetry reconstruction. "
    "Output ONLY valid JSON. Schema: {\"selected\":[\"<id>\",...],\"abort\":false}"
)

async def task_maps3d_curate_images(
    tileH3: str = "",
    candidates: list | None = None,
    targetCount: int = 30,
    minCount: int = 8,
) -> dict:
    """Select the best images for COLMAP reconstruction via LLM scoring.

    Returns selectedIds (list), abort (bool if insufficient coverage).
    """
    candidates = candidates or []
    if not candidates:
        return {"ok": False, "selectedIds": [], "abort": True, "error": "no candidates"}

    # Sort by quality score descending, take top 60 to give LLM a manageable set.
    sorted_cands = sorted(candidates, key=lambda x: float(x.get("qualityScore") or 0), reverse=True)
    pool = sorted_cands[:60]

    if len(pool) < minCount:
        return {"ok": True, "selectedIds": [c["id"] for c in pool], "abort": True,
                "reason": f"only {len(pool)} candidates < minCount {minCount}"}

    # Build compact summary for LLM (avoid passing full URLs in the prompt).
    summaries = [
        {"id": c["id"], "q": round(float(c.get("qualityScore") or 0), 2),
         "angle": round(float(c.get("compassAngle") or 0))}
        for c in pool
    ]
    user = (
        f"Tile H3: {tileH3}\n"
        f"Select {targetCount} images for photogrammetry from the following candidates. "
        f"Prefer diversity of angles (spread compass bearings), highest quality, "
        f"avoid near-duplicate angles. Minimum {minCount} required; set abort=true if impossible.\n"
        f"Candidates:\n{json.dumps(summaries, ensure_ascii=False)}"
    )

    try:
        result = _llm.call_tier_json("fast", system=_CURATE_SYSTEM, user=user, max_tokens=1000)
    except Exception as e:
        # LLM failure: fall back to top-N by quality score.
        selected = [c["id"] for c in pool[:targetCount]]
        return {"ok": True, "selectedIds": selected, "abort": len(selected) < minCount,
                "fallback": f"LLM failed: {e}"}

    if result.get("ok") and isinstance(result.get("data"), dict):
        d = result["data"]
        selected = [str(x) for x in (d.get("selected") or [])][:targetCount]
        abort = bool(d.get("abort", False)) or len(selected) < minCount
        return {"ok": True, "selectedIds": selected, "abort": abort}

    # Fallback
    selected = [c["id"] for c in pool[:targetCount]]
    return {"ok": True, "selectedIds": selected, "abort": len(selected) < minCount}


# ──────────────────────────────────────────────────────────────────────
# Task 5 (step 5): colmapTile — submit job to COLMAP worker pod + poll
# ──────────────────────────────────────────────────────────────────────

async def task_maps3d_colmap_tile(
    tileH3: str = "",
    selectedIds: list | None = None,
    imageUrls: list | None = None,
    denseEnabled: bool = True,
    matcher: str = "exhaustive",
) -> dict:
    """Submit COLMAP SfM reconstruction to the colmap-worker pod and poll for result.

    COLMAP worker API:
      POST /jobs  → { job_id }
      GET  /jobs/{id} → { status: pending|running|done|failed, rawMeshUri, imageCount,
                           errorCode, errorMessage }

    Returns ok, rawMeshUri, imageCount, errorCode, errorMessage.
    """
    if not tileH3 or not selectedIds:
        return {"ok": False, "rawMeshUri": "", "imageCount": 0,
                "errorCode": "MISSING_INPUT", "errorMessage": "tileH3 and selectedIds required"}

    # Build a map of id → thumbUrl from candidates list.
    id_to_url: dict[str, str] = {}
    for item in (imageUrls or []):
        if isinstance(item, dict):
            id_to_url[str(item.get("id", ""))] = str(item.get("thumbUrl", ""))

    image_list = [
        {"id": sid, "url": id_to_url.get(sid, "")}
        for sid in selectedIds
        if sid
    ]

    job_payload = {
        "tileH3": tileH3,
        "images": image_list,
        "denseEnabled": denseEnabled,
        "matcher": matcher,
    }

    try:
        submit_resp = _http_post(f"{_COLMAP_WORKER_URL}/jobs", job_payload, timeout=30.0)
    except RuntimeError as e:
        return {"ok": False, "rawMeshUri": "", "imageCount": 0,
                "errorCode": "SUBMIT_FAILED", "errorMessage": str(e)}

    job_id = submit_resp.get("jobId") or submit_resp.get("job_id") or ""
    if not job_id:
        return {"ok": False, "rawMeshUri": "", "imageCount": 0,
                "errorCode": "NO_JOB_ID", "errorMessage": f"worker response: {submit_resp}"}

    # Poll for completion.
    for _ in range(_COLMAP_MAX_POLLS):
        time.sleep(_COLMAP_POLL_INTERVAL_SEC)
        try:
            status_resp = _http_get(f"{_COLMAP_WORKER_URL}/jobs/{job_id}", timeout=15.0)
        except RuntimeError as e:
            continue  # transient; keep polling

        status = str(status_resp.get("status") or "unknown")
        if status == "done":
            return {
                "ok": True,
                "rawMeshUri": str(status_resp.get("rawMeshUri") or ""),
                "imageCount": int(status_resp.get("imageCount") or 0),
                "errorCode": "",
                "errorMessage": "",
            }
        if status == "failed":
            return {
                "ok": False,
                "rawMeshUri": "",
                "imageCount": int(status_resp.get("imageCount") or 0),
                "errorCode": str(status_resp.get("errorCode") or "COLMAP_FAILED"),
                "errorMessage": str(status_resp.get("errorMessage") or ""),
            }

    return {"ok": False, "rawMeshUri": "", "imageCount": 0,
            "errorCode": "POLL_TIMEOUT", "errorMessage": "COLMAP job did not complete within time budget"}


# ──────────────────────────────────────────────────────────────────────
# Task 4 (step 6 failure): replanReconstruction — LLM + rule-based decision
# ──────────────────────────────────────────────────────────────────────

_REPLAN_SYSTEM = (
    "You decide what to do when a COLMAP 3D reconstruction fails. "
    "Output ONLY valid JSON. Schema: {\"action\":\"retry\"|\"requestMore\"|\"downgradeOsm\"|\"abort\","
    "\"rationale\":\"<one sentence>\"}"
)

async def task_maps3d_replan_reconstruction(
    tileH3: str = "",
    errorCode: str = "",
    errorMessage: str = "",
    imageCount: int = 0,
    attempt: int = 1,
) -> dict:
    """Decide what to do after COLMAP reconstruction fails.

    Actions:
      retry         — re-run with same images (transient error)
      requestMore   — expand image search area (too few images)
      downgradeOsm  — give up photogrammetry, use OSM extrude only
      abort         — permanently park tile (manual review required)
    """
    # Hard rule: abort after 3 attempts regardless.
    if attempt >= 3:
        return {"ok": True, "action": "downgradeOsm",
                "rationale": f"max attempts ({attempt}) reached, downgrading to OSM extrude"}

    # Rule: too few images → request more.
    if imageCount < 5:
        return {"ok": True, "action": "requestMore",
                "rationale": f"only {imageCount} images registered — need wider search area"}

    # Use LLM for nuanced decisions.
    user = (
        f"Tile H3: {tileH3}\n"
        f"Error code: {errorCode or 'UNKNOWN'}\n"
        f"Error message: {errorMessage or '(none)'}\n"
        f"Images that registered: {imageCount}\n"
        f"Attempt number: {attempt}\n"
        "Decide the best recovery action."
    )
    try:
        result = _llm.call_tier_json("fast", system=_REPLAN_SYSTEM, user=user, max_tokens=200)
    except Exception:
        return {"ok": True, "action": "retry", "rationale": "LLM unavailable, defaulting to retry"}

    if result.get("ok") and isinstance(result.get("data"), dict):
        d = result["data"]
        action = str(d.get("action") or "retry")
        if action not in {"retry", "requestMore", "downgradeOsm", "abort"}:
            action = "retry"
        return {"ok": True, "action": action, "rationale": str(d.get("rationale") or "")}

    return {"ok": True, "action": "retry", "rationale": "fallback: LLM parse error"}


# ──────────────────────────────────────────────────────────────────────
# Task 3 (step 7): simplifyAndExport — Open3D simplify via colmap-worker
# ──────────────────────────────────────────────────────────────────────

async def task_maps3d_simplify_and_export(
    tileH3: str = "",
    rawMeshUri: str = "",
    targetTriangles: int = 5000,
    saturate: float = 1.3,
    segmentByFootprint: bool = False,
) -> dict:
    """Simplify raw mesh and export as GLB via the COLMAP worker simplify endpoint.

    COLMAP worker API:
      POST /simplify → { job_id }
      GET  /jobs/{id} → { status, tileMeshUri, triangleCount }
    """
    if not rawMeshUri:
        return {"ok": False, "tileMeshUri": "", "triangleCount": 0,
                "error": "rawMeshUri required"}

    payload = {
        "tileH3": tileH3,
        "rawMeshUri": rawMeshUri,
        "targetTriangles": targetTriangles,
        "saturate": saturate,
        "segmentByFootprint": segmentByFootprint,
    }
    try:
        submit_resp = _http_post(f"{_COLMAP_WORKER_URL}/simplify", payload, timeout=30.0)
    except RuntimeError as e:
        return {"ok": False, "tileMeshUri": "", "triangleCount": 0, "error": str(e)}

    job_id = submit_resp.get("jobId") or submit_resp.get("job_id") or ""
    if not job_id:
        return {"ok": False, "tileMeshUri": "", "triangleCount": 0,
                "error": f"no job_id: {submit_resp}"}

    for _ in range(40):  # 10 min max for simplification
        time.sleep(15)
        try:
            status_resp = _http_get(f"{_COLMAP_WORKER_URL}/jobs/{job_id}", timeout=15.0)
        except RuntimeError:
            continue
        status = str(status_resp.get("status") or "")
        if status == "done":
            return {
                "ok": True,
                "tileMeshUri": str(status_resp.get("tileMeshUri") or ""),
                "triangleCount": int(status_resp.get("triangleCount") or 0),
            }
        if status == "failed":
            return {"ok": False, "tileMeshUri": "", "triangleCount": 0,
                    "error": str(status_resp.get("errorMessage") or "simplify failed")}

    return {"ok": False, "tileMeshUri": "", "triangleCount": 0, "error": "simplify timed out"}


# ──────────────────────────────────────────────────────────────────────
# Task 2 (step 8): visionAnnotate — Murakumo Vision over curated images
# ──────────────────────────────────────────────────────────────────────

_VISION_SYSTEM = (
    "You are a vision analysis assistant for 3D city modelling. "
    "Given a street-level image URL, list visible buildings, businesses, "
    "signage, and landmarks. Output ONLY valid JSON. "
    'Schema: {"detections":[{"label":"<name>","confidence":0.0-1.0,"category":"building"|"business"|"landmark"|"sign"}]}'
)

async def task_maps3d_vision_annotate(
    tileH3: str = "",
    imageRefs: list | None = None,
    minConfidence: float = 0.55,
) -> dict:
    """Run Murakumo Vision over curated Mapillary images.

    imageRefs: list of Mapillary image dicts with id + thumbUrl fields.
    Returns detections: list of {label, confidence, category, imageRef}.
    """
    imageRefs = imageRefs or []
    if not imageRefs:
        return {"ok": True, "detections": []}

    all_detections: list[dict] = []
    seen_labels: set[str] = set()

    # Limit to 10 images to stay within LLM token budget.
    sample = imageRefs[:10]

    for img_ref in sample:
        img_id = str(img_ref.get("id") or "")
        img_url = str(img_ref.get("thumbUrl") or "")
        if not img_url:
            continue

        try:
            result = _llm.call_tier(
                "balanced",
                system="",
                user="",
                max_tokens=600,
                extra={
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _VISION_SYSTEM + "\nImage URL: " + img_url
                             + "\nList all visible named entities."},
                            {"type": "image_url", "image_url": {"url": img_url}},
                        ],
                    }]
                },
            )
        except Exception:
            continue

        raw_content = str(result.get("content") or "")
        # Parse JSON from content.
        try:
            brace = raw_content.find("{")
            end = raw_content.rfind("}") + 1
            if brace >= 0 and end > brace:
                parsed = json.loads(raw_content[brace:end])
                for det in parsed.get("detections") or []:
                    conf = float(det.get("confidence") or 0)
                    label = str(det.get("label") or "").strip()
                    if conf >= minConfidence and label and label not in seen_labels:
                        seen_labels.add(label)
                        all_detections.append({
                            "label": label,
                            "confidence": conf,
                            "category": str(det.get("category") or "building"),
                            "imageRef": img_id,
                        })
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    persisted = _persist_vision_results(tileH3, all_detections)
    return {"ok": True, "detections": all_detections, "persisted": persisted}


# ──────────────────────────────────────────────────────────────────────
# Task 1 (step 9 — reverse topo leaf): linkActor — entity → DID lookup
# ──────────────────────────────────────────────────────────────────────

_LINK_SYSTEM = (
    "You are an entity disambiguation assistant. Given a list of detected entity labels "
    "and a registry of known actor DIDs, map each detection to the best matching actor DID. "
    "Output ONLY valid JSON. "
    'Schema: {"links":[{"label":"<detection label>","actorDid":"did:web:...","confidence":0.0-1.0}]}'
)

async def task_maps3d_link_actor(
    tileH3: str = "",
    detections: list | None = None,
    minConfidence: float = 0.7,
) -> dict:
    """Resolve detected entity labels to actor DIDs via LLM + registry query.

    Returns links: list of {label, actorDid, confidence}.
    """
    detections = detections or []
    if not detections:
        return {"ok": True, "links": []}


    # Query the actor registry for candidate actors. Uses the kotoba Datomic
    # client's Datalog-backed select shim (the prior SELECT-string passed to the
    # Datalog `q()` endpoint never parsed, and its column list was always empty).
    registry_rows: list[dict] = []
    try:
        registry_rows = get_kotoba_client().select_where(
            "vertex_actor_registry",
            "status",
            "active",
            ["did", "handle", "display_name"],
            limit=200,
        )
    except Exception:
        pass  # registry unavailable; proceed with detection-only linkage

    labels = [str(d.get("label") or "") for d in detections if d.get("label")]
    registry_summary = [
        {"did": r.get("did", ""), "handle": r.get("handle", ""), "name": r.get("display_name", "")}
        for r in registry_rows[:50]
    ]

    user = (
        f"Tile H3: {tileH3}\n"
        f"Detected entities:\n{json.dumps(labels, ensure_ascii=False)}\n\n"
        f"Known actors in registry:\n{json.dumps(registry_summary, ensure_ascii=False)}\n\n"
        f"For each detected entity, find the best matching actor DID if confidence >= {minConfidence}. "
        "Only include high-confidence matches. Unknown entities may be omitted."
    )

    try:
        result = _llm.call_tier_json("balanced", system=_LINK_SYSTEM, user=user, max_tokens=800)
    except Exception as e:
        return {"ok": True, "links": [], "warning": f"LLM failed: {e}"}

    if result.get("ok") and isinstance(result.get("data"), dict):
        raw_links = result["data"].get("links") or []
        links = [
            {"label": str(lk.get("label") or ""),
             "actorDid": str(lk.get("actorDid") or ""),
             "confidence": float(lk.get("confidence") or 0)}
            for lk in raw_links
            if float(lk.get("confidence") or 0) >= minConfidence
               and lk.get("actorDid")
        ]
        persisted = _persist_actor_links(tileH3, links)
        return {"ok": True, "links": links, "persisted": persisted}

    return {"ok": True, "links": [], "persisted": 0}


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int = 120_000) -> None:
    """Wire all maps3d task types onto the shared LangServer worker.

    DEPRECATED (Zeebe path): the Zeebe/BPMN-engine execution of processTile is
    being retired in favour of the kotoba + Datomic engine
    ``maps.methods.maps3d-bpmn`` (Clojure), which drives the same flow over the
    Datom log with no external workflow engine. These task *implementations*
    stay live and are reused as injected handlers by the Datomic engine; only
    the Zeebe *worker registration* is deprecated. Do not add new Zeebe-only
    task types here — model new steps in the BPMN process-def datoms instead.
    """

    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    # Registered in reverse topological order (sinks first) matching impl order above.
    t("maps3d.linkActor",            task_maps3d_link_actor,            ms=120_000)
    t("maps3d.visionAnnotate",       task_maps3d_vision_annotate,       ms=300_000)
    t("maps3d.simplifyAndExport",    task_maps3d_simplify_and_export,   ms=600_000)
    t("maps3d.replanReconstruction", task_maps3d_replan_reconstruction, ms=60_000)
    t("maps3d.colmapTile",           task_maps3d_colmap_tile,           ms=3_600_000)
    t("maps3d.curateImages",         task_maps3d_curate_images,         ms=120_000)
    t("maps3d.fetchMapillary",       task_maps3d_fetch_mapillary,       ms=120_000)


__all__ = [
    "register",
    "task_maps3d_fetch_mapillary",
    "task_maps3d_curate_images",
    "task_maps3d_colmap_tile",
    "task_maps3d_replan_reconstruction",
    "task_maps3d_simplify_and_export",
    "task_maps3d_vision_annotate",
    "task_maps3d_link_actor",
]
