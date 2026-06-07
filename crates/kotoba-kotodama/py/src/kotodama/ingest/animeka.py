"""Animeka appview business logic for Zeebe workers."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR_DID = "did:web:animeka.etzhayyim.com"
REPO_DID = "did:web:an1m3k4x.etzhayyim.com"

STRING_KEYS = {
    "title", "name", "displayName", "description", "parentRkey", "workId", "episodeId",
    "sceneId", "cutId", "characterId", "projectId", "convoId", "storyboardId",
    "layoutId", "keyframeId", "retakeId", "targetUri", "stage", "priority",
    "severity", "method", "cameraMode", "lightingMood", "lightingCondition", "slug",
    "author", "writer", "speaker", "trackType", "layerRole", "imageCid", "thumbCid",
    "masterCid", "layersCid", "bgCid", "colorLayersCid", "flatCid", "outputCid",
    "coverCid", "refSheetCid", "materialMapCid", "assetCid", "mimeType", "imageUrl",
    "headingJp", "location", "timeOfDay", "mood", "status",
}
NUMERIC_KEYS = {
    "episodeNum", "sceneNum", "cutNum", "frameNum", "durationFrames", "durationSec",
    "fps", "inFrame", "outFrame", "timecodeFrame", "width", "height", "x", "y", "w", "h",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def gen_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _snake(name: str) -> str:
    out = ""
    for ch in name:
        out += f"_{ch.lower()}" if ch.isupper() else ch
    return out.lstrip("_")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _typed(record: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in STRING_KEYS:
        value = record.get(key)
        if value is not None and value != "":
            out[_snake(key)] = _str(value)
    for key in NUMERIC_KEYS:
        value = record.get(key)
        if isinstance(value, (int, float)):
            out[_snake(key)] = value
    if isinstance(record.get("stageStatus"), dict):
        out["stage_status"] = _json(record["stageStatus"])
    if isinstance(record.get("assignees"), dict):
        out["assignees"] = _json(record["assignees"])
    return out


def _write(collection: str, rkey: str, record: dict[str, Any]) -> dict[str, str]:
    created = _str(record.get("createdAt") or record.get("created_at") or now_iso())
    kind = collection.rsplit(".", 1)[-1]
    uri = f"at://{REPO_DID}/{collection}/{rkey}"
    row = {
        "vertex_id": uri,
        "created_date": created[:10],
        "sensitivity_ord": 100,
        "owner_did": REPO_DID,
        "rkey": rkey,
        "repo": REPO_DID,
        "did": REPO_DID,
        "collection": collection,
        "label": kind,
        "kind": kind,
        "created_at": created,
        "props": _json(record),
        "actor_did": ACTOR_DID,
        "org_did": "anon",
        **_typed(record),
    }
    get_kotoba_client().insert_row("vertex_animeka", row)
    return {"uri": uri, "cid": ""}


def _list(collection: str, where: dict[str, Any] | None = None, order: str = "created_at", desc: bool = True, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    # R0: Multiple predicates, ordering, and pagination handled by in-Python filter
    all_results = get_kotoba_client().select_where("view_animeka_record_flat", "repo", REPO_DID, limit=2000)

    filtered_results = []
    full_where = {"collection": collection, **(where or {})}
    for row in all_results:
        match = True
        for k, v in full_where.items():
            if row.get(k) != v:
                match = False
                break
        if match:
            filtered_results.append(row)

    # Apply ordering
    if order in filtered_results[0] if filtered_results else []:
        filtered_results.sort(key=lambda x: x.get(order), reverse=desc)

    # Apply pagination
    start = max(int(offset or 0), 0)
    end = start + min(max(int(limit or 100), 1), 500)

    return filtered_results[start:end]


def _count(collection: str, where: dict[str, Any] | None = None) -> int:
    where = {"collection": collection, **(where or {})}
    if len(where) == 1:
        key, value = list(where.items())[0]
        return int(get_kotoba_client().aggregate_where("view_animeka_record_flat", "count", "*", key, value))
    else:
        # R0: Multiple predicates handled by in-Python filter
        results = get_kotoba_client().select_where("view_animeka_record_flat", "repo", REPO_DID, limit=2000)
        count = 0
        for row in results:
            match = True
            for k, v in where.items():
                if row.get(k) != v:
                    match = False
                    break
            if match:
                count += 1
        return count


def _get(collection: str, rkey: str) -> dict[str, Any] | None:
    # R0: Multiple predicates (collection, rkey) handled by in-Python filter
    results = get_kotoba_client().select_where("view_animeka_record_flat", "repo", REPO_DID, limit=10)
    for row in results:
        if row.get("collection") == collection and row.get("rkey") == rkey:
            return row
    return None


def create_work(**req: Any) -> dict[str, Any]:
    work_id = _str(req.get("id") or gen_id("work"))
    record = {
        "title": _str(req.get("title") or "Untitled"),
        "titleEN": _str(req.get("titleEN")),
        "slug": _str(req.get("slug") or work_id),
        "genre": _str(req.get("genre")),
        "status": _str(req.get("status") or "planning"),
        "description": _str(req.get("synopsis")),
        "episodeCount": int(req.get("episodeCount") or 0),
        "fps": int(req.get("fps") or 24),
        "coverCid": _str(req.get("coverCid")),
    }
    out = _write("com.etzhayyim.apps.animeka.work", work_id, record)
    return {"ok": True, "id": work_id, **out, "did": f"{ACTOR_DID}:work:{record['slug']}", "title": record["title"], "status": record["status"]}


def list_works(limit: int = 50, offset: int = 0, status: str = "", **_: Any) -> dict[str, Any]:
    where = {"status": status} if status else {}
    items = _list("com.etzhayyim.apps.animeka.work", where, limit=limit, offset=offset)
    return {"ok": True, "items": items, "total": _count("com.etzhayyim.apps.animeka.work", where), "offset": offset, "limit": limit}


def add_episode(**req: Any) -> dict[str, Any]:
    episode_id = _str(req.get("id") or gen_id("ep"))
    convo_id = gen_id("convo")
    record = {
        "workId": _str(req.get("workId")),
        "episodeId": episode_id,
        "episodeNum": int(req.get("episodeNum") or 0),
        "title": _str(req.get("titleJP") or req.get("titleEN") or f"Episode {req.get('episodeNum') or ''}"),
        "convoId": convo_id,
        "durationSec": float(req.get("durationSec") or 1410),
        "fps": int(req.get("fps") or 24),
        "status": "planning",
        "thumbCid": _str(req.get("thumbCid")),
    }
    out = _write("com.etzhayyim.apps.animeka.episode", episode_id, record)
    return {"ok": True, **out, "convoId": convo_id}


def list_episodes(workId: str = "", status: str = "", limit: int = 50, offset: int = 0, **_: Any) -> dict[str, Any]:
    where = {k: v for k, v in {"work_id": workId, "status": status}.items() if v}
    items = _list("com.etzhayyim.apps.animeka.episode", where, order="episode_num", desc=False, limit=limit, offset=offset)
    return {"ok": True, "items": items, "total": _count("com.etzhayyim.apps.animeka.episode", where), "offset": offset, "limit": limit}


def publish_episode(episodeId: str = "", status: str = "published", **req: Any) -> dict[str, Any]:
    if not episodeId:
        return {"ok": False, "error": "episodeId required"}
    rkey = episodeId.rsplit("/", 1)[-1]
    existing = _get("com.etzhayyim.apps.animeka.episode", rkey) or {}
    record = {**existing, "status": status, "masterCid": _str(req.get("masterCid")), "thumbCid": _str(req.get("thumbCid")), "title": _str(req.get("titleJP") or existing.get("title") or f"Episode {rkey}")}
    out = _write("com.etzhayyim.apps.animeka.episode", rkey, record)
    return {"ok": True, "episodeId": rkey, "status": status, "emitted": 0, "postUri": out["uri"], "episodeUri": out["uri"], "domainWriteOk": True}


def add_cut(**req: Any) -> dict[str, Any]:
    cut_id = _str(req.get("id") or gen_id("cut"))
    record = {
        "sceneId": _str(req.get("sceneId")),
        "episodeId": _str(req.get("episodeId")),
        "cutId": cut_id,
        "cutNum": int(req.get("cutNum") or 0),
        "durationFrames": int(req.get("durationFrames") or 24),
        "fps": int(req.get("fps") or 24),
        "cameraMode": _str(req.get("cameraMode") or "still"),
        "cameraNote": _str(req.get("cameraNote")),
        "dialogue": _str(req.get("dialogueSummary")),
        "stageStatus": {"script": "approved", "storyboard": "pending", "layout": "none", "keyAnim": "none", "inbetween": "none", "colorDesign": "none", "finish": "none", "background": "none", "composite": "none", "edit": "none", "sound": "none", "delivery": "none"},
        "assignees": {},
        "priority": "normal",
    }
    out = _write("com.etzhayyim.apps.animeka.cut", cut_id, record)
    return {"ok": True, **out, "did": f"{ACTOR_DID}:cut:{cut_id}", "cutNum": record["cutNum"]}


def list_cuts(episodeId: str = "", sceneId: str = "", priority: str = "", limit: int = 100, offset: int = 0, **_: Any) -> dict[str, Any]:
    where = {k: v for k, v in {"episode_id": episodeId, "scene_id": sceneId, "priority": priority}.items() if v}
    items = _list("com.etzhayyim.apps.animeka.cut", where, order="cut_num", desc=False, limit=limit, offset=offset)
    return {"ok": True, "items": items, "total": _count("com.etzhayyim.apps.animeka.cut", where), "offset": offset, "limit": limit}


def get_cut(cutId: str = "", **_: Any) -> dict[str, Any]:
    if not cutId:
        return {"ok": False, "error": "cutId required"}
    rkey = cutId.rsplit("/", 1)[-1]
    collections = {
        "storyboards": "storyboard", "layouts": "layout", "keyframes": "keyframe",
        "inbetweens": "inbetween", "colorTraces": "colorTrace", "backgrounds": "background",
        "composites": "composite", "soundCues": "soundCue", "retakes": "retake",
    }
    out: dict[str, Any] = {"ok": True, "cut": _get("com.etzhayyim.apps.animeka.cut", rkey)}
    for key, suffix in collections.items():
        order = "frame_num" if key in {"keyframes", "inbetweens", "colorTraces"} else "created_at"
        out[key] = _list(f"com.etzhayyim.apps.animeka.{suffix}", {"cut_id": rkey}, order=order, desc=False, limit=500)
    return out


def update_cut_stage(cutId: str = "", stage: str = "", status: str = "", assigneeDid: str = "", **_: Any) -> dict[str, Any]:
    if not cutId or not stage:
        return {"ok": False, "error": "cutId + stage required"}
    rkey = cutId.rsplit("/", 1)[-1]
    existing = _get("com.etzhayyim.apps.animeka.cut", rkey) or {}
    stage_status = _parse_map(existing.get("stage_status") or existing.get("stageStatus"))
    assignees = _parse_map(existing.get("assignees"))
    if status:
        stage_status[stage] = status
    if assigneeDid:
        assignees[stage] = assigneeDid
    _write("com.etzhayyim.apps.animeka.cut", rkey, {**existing, "stageStatus": stage_status, "assignees": assignees})
    return {"ok": True, "cutId": rkey, "stage": stage, "status": status, "derivedCount": 0}


def _parse_map(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def submit_retake(**req: Any) -> dict[str, Any]:
    retake_id = gen_id("rt")
    cut_id = _str(req.get("cutId")).rsplit("/", 1)[-1]
    stage = _str(req.get("stage"))
    out = _write("com.etzhayyim.apps.animeka.retake", retake_id, {
        "targetUri": _str(req.get("targetUri")),
        "cutId": cut_id,
        "retakeId": retake_id,
        "stage": stage,
        "comment": _str(req.get("comment")),
        "severity": _str(req.get("severity") or "minor"),
        "timecodeFrame": int(req.get("timecodeFrame") or 0),
        "status": "open",
        "priority": "retake",
    })
    if cut_id:
        update_cut_stage(cutId=cut_id, stage=stage, status="retake")
        existing = _get("com.etzhayyim.apps.animeka.cut", cut_id) or {}
        _write("com.etzhayyim.apps.animeka.cut", cut_id, {**existing, "priority": "retake"})
    return {"ok": True, **out}


def resolve_retake(retakeId: str = "", status: str = "resolved", resolvedByUri: str = "", **_: Any) -> dict[str, Any]:
    if not retakeId:
        return {"ok": False, "error": "retakeId required"}
    rkey = retakeId.rsplit("/", 1)[-1]
    existing = _get("com.etzhayyim.apps.animeka.retake", rkey) or {}
    _write("com.etzhayyim.apps.animeka.retake", rkey, {**existing, "status": status, "resolvedByUri": resolvedByUri})
    cut_id = _str(existing.get("cut_id") or existing.get("cutId"))
    cut_priority = "normal"
    if cut_id and status == "resolved" and _count("com.etzhayyim.apps.animeka.retake", {"cut_id": cut_id, "status": "open"}) == 0:
        cut = _get("com.etzhayyim.apps.animeka.cut", cut_id) or {}
        _write("com.etzhayyim.apps.animeka.cut", cut_id, {**cut, "priority": "normal"})
    elif cut_id:
        cut_priority = "retake"
    return {"ok": True, "retakeId": rkey, "status": status, "cutPriority": cut_priority}


def list_retakes(episodeId: str = "", cutId: str = "", stage: str = "", status: str = "", assignee: str = "", limit: int = 50, offset: int = 0, **_: Any) -> dict[str, Any]:
    where = {k: v for k, v in {"episode_id": episodeId, "cut_id": cutId, "stage": stage, "status": status, "author": assignee}.items() if v}
    items = _list("com.etzhayyim.apps.animeka.retake", where, limit=limit, offset=offset)
    return {"ok": True, "items": items, "total": _count("com.etzhayyim.apps.animeka.retake", where), "offset": offset, "limit": limit}


def health(**_: Any) -> dict[str, Any]:
    return {"ok": True, "status": "ok", "agent": "animeka", "nanoid": "an1m3k4x", "did": ACTOR_DID, "ts": now_iso()}
