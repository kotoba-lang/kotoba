"""Game Play Uploader handlers for BPMN + Zeebe."""

from datetime import datetime, timezone
import json
import time
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:game-play-uploader.etzhayyim.com"
RATE_JPY_PER_HOUR = 100
COLLECTION_TABLES = {
    "com.etzhayyim.apps.gamePlayUploader.participant": "vertex_game_play_participant",
    "com.etzhayyim.apps.gamePlayUploader.uploadSession": "vertex_game_play_upload_session",
    "com.etzhayyim.apps.gamePlayUploader.upload": "vertex_game_play_upload",
    "com.etzhayyim.apps.gamePlayUploader.review": "vertex_game_play_review",
    "com.etzhayyim.apps.gamePlayUploader.reward": "vertex_game_play_reward",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _s(value: Any, default: str = "") -> str:
    return str(value if value is not None else default)


def _num(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _vertex_id(collection: str, record_id: str) -> str:
    return f"at://{OWNER_DID}/{collection}/{record_id}"


def _edge_id(table: str, src: str, dst: str, relation: str) -> str:
    return f"{table}:{uuid5(NAMESPACE_URL, f'{src}|{dst}|{relation}')}"


def _typed_values(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "participant":
        return {
            "participant_id": _s(payload.get("participantId")),
            "display_name": _s(payload.get("displayName")),
            "age_band": _s(payload.get("ageBand")),
            "payout_handle": _s(payload.get("payoutHandle")),
        }
    if kind == "uploadSession":
        return {
            "game_title": _s(payload.get("gameTitle")),
            "platform": _s(payload.get("platform")),
            "duration_sec": _num(payload.get("durationSec")),
            "capture_started_at": _s(payload.get("captureStartedAt")),
        }
    if kind == "upload":
        return {
            "object_uri": _s(payload.get("objectUri")),
            "duration_sec": _num(payload.get("durationSec")),
            "sha256": _s(payload.get("sha256")),
        }
    if kind == "review":
        return {
            "review_id": _s(payload.get("reviewId")),
            "decision": _s(payload.get("decision")),
            "reviewer_did": _s(payload.get("reviewerDid")),
            "quality_score": _num(payload.get("qualityScore")),
            "reward_estimate_jpy": _num(payload.get("rewardEstimateJpy")),
        }
    if kind == "reward":
        return {"reward_jpy": _num(payload.get("rewardJpy"))}
    return {}


def _write_edge(table: str, src: str, dst: str, relation: str, payload: dict[str, Any], created_at: str) -> None:
    edge_row = {
        "edge_id": _edge_id(table, src, dst, relation),
        "src_vid": src,
        "dst_vid": dst,
        "relation_kind": relation,
        "value_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        "created_at": created_at,
        "updated_at": _s(payload.get("updatedAt")) or created_at,
        "owner_did": OWNER_DID,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row(table, edge_row)


def _write_related_edges(collection: str, kind: str, record_id: str, payload: dict[str, Any], created_at: str) -> None:
    vertex_id = _vertex_id(collection, record_id)
    if kind == "uploadSession":
        participant = _s(payload.get("participantDid"))
        if participant:
            _write_edge("edge_game_play_participant_session", _vertex_id("com.etzhayyim.apps.gamePlayUploader.participant", participant), vertex_id, "created_upload_session", payload, created_at)
    elif kind == "upload":
        session_id = _s(payload.get("sessionId"))
        if session_id:
            _write_edge("edge_game_play_session_upload", _vertex_id("com.etzhayyim.apps.gamePlayUploader.uploadSession", session_id), vertex_id, "has_upload", payload, created_at)
    elif kind == "review":
        upload_id = _s(payload.get("uploadId"))
        if upload_id:
            _write_edge("edge_game_play_upload_review", _vertex_id("com.etzhayyim.apps.gamePlayUploader.upload", upload_id), vertex_id, "reviewed_by", payload, created_at)
    elif kind == "reward":
        upload_id = _s(payload.get("uploadId"))
        if upload_id:
            _write_edge("edge_game_play_upload_reward", _vertex_id("com.etzhayyim.apps.gamePlayUploader.upload", upload_id), vertex_id, "earned_reward", payload, created_at)


def _record(collection: str, kind: str, payload: dict[str, Any], record_id: str | None = None) -> dict[str, Any]:
    table = COLLECTION_TABLES.get(collection)
    if table is None:
        raise ValueError(f"unsupported game play uploader collection: {collection}")
    rid = record_id or _id(kind)
    created = _s(payload.get("createdAt") or payload.get("updatedAt") or now_iso())
    rec = {**payload, "id": payload.get("id") or rid, "createdAt": created}
    typed = _typed_values(kind, rec)
    values = {
        "vertex_id": _vertex_id(collection, rid),
        "record_id": rid,
        "owner_did": OWNER_DID,
        "participant_did": _s(payload.get("participantDid")) or None,
        "session_id": _s(payload.get("sessionId")) or None,
        "upload_id": _s(payload.get("uploadId")) or None,
        "label": _s(payload.get("displayName") or payload.get("gameTitle") or payload.get("objectUri") or kind),
        "status": _s(payload.get("status")),
        "value_json": json.dumps(rec, ensure_ascii=False, sort_keys=True),
        "created_at": created,
        "updated_at": _s(payload.get("updatedAt")) or created,
        "sensitivity_ord": 2,
        **typed,
    }
    get_kotoba_client().insert_row(table, values)
    _write_related_edges(collection, kind, rid, rec, created)
    return rec


def _list(collection: str, where_sql: str = "", params: tuple[Any, ...] = (), limit: int = 500) -> list[dict[str, Any]]:
    table = COLLECTION_TABLES.get(collection)
    if table is None:
        return []

    client = get_kotoba_client()
    raw_db_rows: list[dict] = [] # These will be dicts from kotoba client, with snake_case keys

    # Case 1: Specific upload_id lookup (single result expected)
    if where_sql == "AND upload_id=%s" and params and len(params) == 1:
        row = client.select_first_where(table, "record_id", params[0], columns=["value_json", "created_at"])
        if row:
            raw_db_rows.append(row)
    # Case 2: Specific participant_did lookup (multiple results possible)
    elif where_sql == "AND participant_did=%s" and params and len(params) == 1:
        raw_db_rows = client.select_where(table, "participant_did", params[0], columns=["value_json", "created_at"], limit=limit)
    # Case 3: Fetch all records (no specific WHERE clause, or complex WHERE not handled by shims)
    else:
        # R0: Fetching all records for a table using a Datalog `q` query and then sorting/limiting/filtering in Python.
        # This is because `select_where` requires a specific column and value predicate, and `_list`
        # can be called without such predicates or with dynamic SQL.
        query_edn = f"""
        [:find ?v_json ?c_at
         :where [?e :db/doc "{table}"] [?e :value_json ?v_json] [?e :created_at ?c_at]]
        """
        results_from_q = client.q(query_edn)
        for v_json, c_at in results_from_q:
            raw_db_rows.append({"value_json": v_json, "created_at": c_at})

        # Apply sorting and limit after fetching all.
        raw_db_rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        raw_db_rows = raw_db_rows[:limit]


    out: list[dict[str, Any]] = []
    for row in raw_db_rows:
        try:
            # `value_json` could be a raw string or already deserialized by `kotoba_datomic`
            # Ensure it's a string for json.loads
            json_str = row["value_json"] if isinstance(row["value_json"], str) else json.dumps(row["value_json"])
            parsed = json.loads(json_str)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def _reward(duration_sec: int, rate: int = RATE_JPY_PER_HOUR) -> int:
    return int(round((max(0, duration_sec) / 3600) * max(0, rate)))


def register_participant(participantDid: Any = None, displayName: Any = None, ageBand: Any = "unknown", payoutHandle: Any = None, guardianConsentRef: Any = None, **_: Any) -> dict[str, Any]:
    participant_did = _s(participantDid)
    if not participant_did:
        return {"error": "participantDid required"}
    participant_id = _id("player")
    _record("com.etzhayyim.apps.gamePlayUploader.participant", "participant", {
        "participantId": participant_id,
        "participantDid": participant_did,
        "displayName": _s(displayName),
        "ageBand": _s(ageBand or "unknown"),
        "payoutHandle": _s(payoutHandle),
        "guardianConsentRef": _s(guardianConsentRef),
        "status": "registered",
    }, participant_id)
    return {"participantId": participant_id, "status": "registered"}


def create_upload_session(participantDid: Any = None, gameTitle: Any = None, platform: Any = None, durationSec: Any = 0, captureStartedAt: Any = None, **_: Any) -> dict[str, Any]:
    participant_did = _s(participantDid)
    game_title = _s(gameTitle)
    if not participant_did or not game_title:
        return {"error": "participantDid and gameTitle required"}
    session_id = _id("session")
    object_key = f"game-play-uploader/{participant_did.replace(':', '_')}/{session_id}.mp4"
    upload_intent = {
        "provider": "backend-signed-object-storage",
        "objectKey": object_key,
        "contentType": "video/mp4",
        "expiresInSec": 900,
    }
    session = {
        "sessionId": session_id,
        "participantDid": participant_did,
        "gameTitle": game_title,
        "platform": _s(platform),
        "durationSec": _num(durationSec),
        "captureStartedAt": _s(captureStartedAt),
        "uploadIntent": upload_intent,
        "status": "awaitingUpload",
    }
    _record("com.etzhayyim.apps.gamePlayUploader.uploadSession", "uploadSession", session, session_id)
    return {"sessionId": session_id, "uploadIntent": upload_intent}


def record_gameplay_upload(sessionId: Any = None, objectUri: Any = None, durationSec: Any = 0, sha256: Any = None, metadata: Any = None, **_: Any) -> dict[str, Any]:
    session_id = _s(sessionId)
    object_uri = _s(objectUri)
    if not session_id or not object_uri:
        return {"error": "sessionId and objectUri required"}
    upload_id = _id("upload")
    upload = {
        "uploadId": upload_id,
        "sessionId": session_id,
        "objectUri": object_uri,
        "durationSec": _num(durationSec),
        "sha256": _s(sha256),
        "metadata": metadata if isinstance(metadata, dict) else {},
        "status": "pendingReview",
    }
    _record("com.etzhayyim.apps.gamePlayUploader.upload", "upload", upload, upload_id)
    return {"uploadId": upload_id, "status": "pendingReview"}


def review_upload(uploadId: Any = None, decision: Any = None, reviewerDid: Any = None, notes: Any = None, qualityScore: Any = None, **_: Any) -> dict[str, Any]:
    upload_id = _s(uploadId)
    decision_s = _s(decision)
    if not upload_id or decision_s not in {"approved", "rejected", "needsReview"}:
        return {"error": "uploadId and valid decision required"}
    uploads = _list("com.etzhayyim.apps.gamePlayUploader.upload", "AND upload_id=%s", (upload_id,), 1)
    duration = _num(uploads[0].get("durationSec") if uploads else 0)
    reward = _reward(duration) if decision_s == "approved" else 0
    review = {
        "reviewId": _id("review"),
        "uploadId": upload_id,
        "decision": decision_s,
        "reviewerDid": _s(reviewerDid),
        "notes": _s(notes),
        "qualityScore": qualityScore,
        "rewardEstimateJpy": reward,
    }
    _record("com.etzhayyim.apps.gamePlayUploader.review", "review", review, review["reviewId"])
    if reward > 0:
        _record("com.etzhayyim.apps.gamePlayUploader.reward", "reward", {"uploadId": upload_id, "rewardJpy": reward, "status": "estimated"})
    return {"uploadId": upload_id, "decision": decision_s, "rewardEstimateJpy": reward}


def calculate_reward(durationSec: Any = 0, rateJpyPerHour: Any = RATE_JPY_PER_HOUR, **_: Any) -> dict[str, Any]:
    duration = _num(durationSec)
    rate = _num(rateJpyPerHour, RATE_JPY_PER_HOUR)
    return {"rewardJpy": _reward(duration, rate), "rateJpyPerHour": rate, "durationSec": duration}


def get_campaign_status(participantDid: Any = None, **_: Any) -> dict[str, Any]:
    participant_did = _s(participantDid)
    where = "AND participant_did=%s" if participant_did else ""
    params: tuple[Any, ...] = (participant_did,) if participant_did else ()
    participants = _list("com.etzhayyim.apps.gamePlayUploader.participant", where, params)
    uploads = _list("com.etzhayyim.apps.gamePlayUploader.upload")
    reviews = _list("com.etzhayyim.apps.gamePlayUploader.review")
    approved_upload_ids = {_s(r.get("uploadId")) for r in reviews if _s(r.get("decision")) == "approved"}
    approved_duration = sum(_num(u.get("durationSec")) for u in uploads if _s(u.get("uploadId")) in approved_upload_ids)
    return {
        "participants": len(participants) if participant_did else len(_list("com.etzhayyim.apps.gamePlayUploader.participant")),
        "uploads": len(uploads),
        "approvedDurationSec": approved_duration,
        "rewardJpy": _reward(approved_duration),
    }
