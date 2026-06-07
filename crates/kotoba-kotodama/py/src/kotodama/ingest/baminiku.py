"""Baminiku KAMI Engine live-stream handlers for BPMN + Zeebe."""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:baminiku.etzhayyim.com"
KAMI_SDK = "etzhayyim:kami@1.0.0"
COLLECTION_TABLES = {
    "com.etzhayyim.apps.baminiku.agent": "vertex_baminiku_agent_profile",
    "com.etzhayyim.apps.baminiku.stream": "vertex_baminiku_stream",
    "com.etzhayyim.apps.baminiku.stagePatch": "vertex_baminiku_stage_patch",
    "com.etzhayyim.apps.baminiku.chat": "vertex_baminiku_chat",
    "com.etzhayyim.apps.baminiku.tip": "vertex_baminiku_tip",
    "com.etzhayyim.apps.baminiku.track": "vertex_baminiku_track",
    "com.etzhayyim.apps.baminiku.trackEvent": "vertex_baminiku_track_event",
}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _s(value: Any, default: str = "") -> str:
    return str(value if value is not None else default)


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _arr(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _num(value: Any, default: float = 0) -> float:
    try:
        n = float(value)
        return n if math.isfinite(n) else default
    except (TypeError, ValueError):
        return default





def _vertex_id(collection: str, record_id: str) -> str:
    return f"at://{OWNER_DID}/{collection}/{record_id}"


def _edge_id(table: str, src: str, dst: str, relation: str) -> str:
    return f"{table}:{uuid5(NAMESPACE_URL, f'{src}|{dst}|{relation}')}"


def _record_label(kind: str, rec: dict[str, Any]) -> str:
    return _s(rec.get("displayName") or rec.get("title") or rec.get("text") or rec.get("message") or rec.get("reason") or kind)


def _typed_columns(kind: str) -> list[str]:
    return {
        "agentProfile": ["display_name", "voice_preset", "personality"],
        "stream": ["title", "stage_preset", "visibility", "scheduled_at", "knp_room"],
        "chat": ["viewer_did", "convo_id", "text"],
        "tip": ["viewer_did", "amount", "currency", "effect_type"],
        "track": ["title", "artist", "audio_uri", "requested_by_did", "queue_position"],
        "trackSkip": ["skipped_track_id", "reason"],
    }.get(kind, [])


def _typed_values(kind: str, rec: dict[str, Any]) -> dict[str, Any]:
    if kind == "agentProfile":
        return {
            "display_name": _s(rec.get("displayName")),
            "voice_preset": _s(rec.get("voicePreset")),
            "personality": _s(rec.get("personality")),
        }
    if kind == "stream":
        return {
            "title": _s(rec.get("title")),
            "stage_preset": _s(rec.get("stagePreset")),
            "visibility": _s(rec.get("visibility")),
            "scheduled_at": _s(rec.get("scheduledAt")),
            "knp_room": _s(rec.get("knpRoom")),
        }
    if kind == "chat":
        return {
            "viewer_did": _s(rec.get("viewerDid")),
            "convo_id": _s(rec.get("convoId")),
            "text": _s(rec.get("text")),
        }
    if kind == "tip":
        return {
            "viewer_did": _s(rec.get("viewerDid")),
            "amount": _num(rec.get("amount")),
            "currency": _s(rec.get("currency")),
            "effect_type": _s(rec.get("effectType")),
        }
    if kind == "track":
        return {
            "title": _s(rec.get("title")),
            "artist": _s(rec.get("artist")),
            "audio_uri": _s(rec.get("audioUri")),
            "requested_by_did": _s(rec.get("requestedByDid")),
            "queue_position": int(_num(rec.get("queuePosition"))),
        }
    if kind == "trackSkip":
        return {
            "skipped_track_id": _s(rec.get("skippedTrackId")),
            "reason": _s(rec.get("reason")),
        }
    return {}


def _write_edge(table: str, src: str, dst: str, relation: str, value: dict[str, Any], created_at: str) -> None:
    edge_data = {
        "edge_id": _edge_id(table, src, dst, relation),
        "src_vid": src,
        "dst_vid": dst,
        "relation_kind": relation,
        "value_json": json.dumps(value, ensure_ascii=False, sort_keys=True),
        "created_at": created_at,
        "updated_at": created_at,
        "owner_did": OWNER_DID,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row(table, edge_data)


def _write_related_edges(collection: str, kind: str, rec: dict[str, Any], vertex_id: str, created_at: str) -> None:
    stream_id = _s(rec.get("streamId"))
    stream_vid = _vertex_id("com.etzhayyim.apps.baminiku.stream", stream_id) if stream_id else ""
    if kind == "stream":
        agent_did = _s(rec.get("agentDid"))
        if agent_did:
            _write_edge("edge_baminiku_stream_agent", vertex_id, _vertex_id("com.etzhayyim.apps.baminiku.agent", agent_did), "hosted_by_agent", rec, created_at)
    elif collection == "com.etzhayyim.apps.baminiku.stagePatch" and stream_vid:
        _write_edge("edge_baminiku_stream_stage_patch", stream_vid, vertex_id, "has_stage_patch", rec, created_at)
    elif kind == "chat" and stream_vid:
        _write_edge("edge_baminiku_stream_chat", stream_vid, vertex_id, "has_chat", rec, created_at)
    elif kind == "tip" and stream_vid:
        _write_edge("edge_baminiku_stream_tip", stream_vid, vertex_id, "has_tip", rec, created_at)
    elif kind == "track" and stream_vid:
        _write_edge("edge_baminiku_stream_track", stream_vid, vertex_id, "has_track", rec, created_at)
    elif collection == "com.etzhayyim.apps.baminiku.trackEvent" and stream_vid:
        _write_edge("edge_baminiku_stream_track_event", stream_vid, vertex_id, "has_track_event", rec, created_at)


def _record(
    collection: str,
    kind: str,
    payload: dict[str, Any],
    record_id: str | None = None,
    stream_id: str | None = None,
    agent_did: str | None = None,
) -> dict[str, Any]:
    table = COLLECTION_TABLES.get(collection)
    if table is None:
        raise ValueError(f"unsupported baminiku collection: {collection}")
    rid = record_id or _id(kind)
    created_at = _s(payload.get("createdAt") or payload.get("updatedAt") or now_iso())
    rec = {**payload, "id": payload.get("id") or rid, "createdAt": created_at}
    vertex_id = _vertex_id(collection, rid)
    typed = _typed_values(kind, rec)
    values = {
        "vertex_id": vertex_id,
        "record_id": rid,
        "owner_did": OWNER_DID,
        "label": _record_label(kind, rec),
        "status": _s(rec.get("status")),
        "stream_id": stream_id or _s(payload.get("streamId")) or None,
        "agent_did": agent_did or _s(payload.get("agentDid")) or None,
        "value_json": json.dumps(rec, ensure_ascii=False, sort_keys=True),
        "created_at": created_at,
        "updated_at": _s(payload.get("updatedAt")) or created_at,
        "sensitivity_ord": 2,
        **typed,
    }
    # The `columns`, `placeholders`, and `updates` are no longer needed for insert_row
    # which takes a dictionary directly.
    get_kotoba_client().insert_row(table, values)
    _write_related_edges(collection, kind, rec, vertex_id, created_at)
    return rec


def _list_records(collection: str, where_sql: str = "", params: tuple[Any, ...] = (), limit: int = 100) -> list[dict[str, Any]]:
    table = COLLECTION_TABLES.get(collection)
    if table is None:
        raise ValueError(f"unsupported baminiku collection: {collection}")

    where_column: str | None = None
    where_value: Any = None

    # Parse where_sql for simple "AND column=%s" patterns
    if where_sql.startswith("AND ") and where_sql.endswith("=%s") and params:
        # Extract column name, assuming format "AND col=%s"
        where_column = where_sql[4:-3].strip()
        where_value = params[0]

    raw_records: list[dict[str, Any]] = []
    if where_column and where_value:
        # Use select_where for single equality predicates
        # Fetch all necessary columns for later processing (sorting, JSON parsing)
        # Fetch a higher limit to allow for in-Python sorting and limiting.
        # R0: Fetching a broader set of records to allow for in-Python sorting and limiting
        # since `select_where` does not support `ORDER BY` or direct `LIMIT` based on sorted results.
        raw_records = get_kotoba_client().select_where(
            table,
            where_column,
            where_value,
            columns=["value_json", "created_at"],
            limit=500  # Fetch up to 500 to match original limit range
        )

        # R0: In-Python sorting by created_at DESC.
        raw_records.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # R0: In-Python limiting to the requested number of records.
        # The original SQL had LIMIT max(1, min(limit, 500)).
        raw_records = raw_records[:max(1, min(limit, 500))]
    else:
        # This case is not expected to be hit by existing calls to _list_records,
        # as all calls currently provide a simple "AND column=%s" predicate.
        # If a general "select all" or complex WHERE clause were needed,
        # it would require a raw Datalog query via `q()`.
        pass # No changes needed here as current uses are covered by the if block.

    out: list[dict[str, Any]] = []
    for record_dict in raw_records:
        # Assuming record_dict contains 'value_json' as a string
        record_json_str = record_dict.get("value_json")
        if isinstance(record_json_str, str):
            try:
                parsed = json.loads(record_json_str)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, dict):
                out.append(parsed)
    return out


def _kami(action: str, payload: dict[str, Any], stream_id: str | None = None) -> dict[str, Any]:
    return {
        "sdk": KAMI_SDK,
        "target": "kami-engine-sdk",
        "transport": "knp-webtransport",
        "streamId": stream_id,
        "action": action,
        "payload": payload,
        "issuedAt": now_iso(),
    }


def _default_scene(stream_id: str, title: str, stage_preset: str) -> dict[str, Any]:
    return {
        "@context": "https://etzhayyim.com/ns/kami/live-stage/v1",
        "@type": "KamiIsland",
        "id": stream_id,
        "genre": "social",
        "title": title,
        "stagePreset": stage_preset,
        "entities": [
            {"id": "stage", "kind": "cube", "position": [0, 0, 0], "scale": [8, 0.5, 6], "material": {"color": "#24112f"}},
            {"id": "backdrop", "kind": "cube", "position": [0, 3, -3], "scale": [10, 6, 0.2], "material": {"color": "#101827"}},
            {"id": "spotlight-left", "kind": "light", "lightType": "spot", "position": [-3, 5, 2], "color": "#ffd7a1"},
            {"id": "spotlight-right", "kind": "light", "lightType": "spot", "position": [3, 5, 2], "color": "#a7c7ff"},
            {"id": "agent-spawn", "kind": "spawnPoint", "position": [0, 0.5, 0]},
            {"id": "audience", "kind": "plane", "position": [0, 0, 5], "scale": [12, 8, 1]},
        ],
    }


def _default_appearance(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "face": _s(raw.get("face"), "round"),
        "skinHue": _num(raw.get("skinHue"), 0.07),
        "eye": _s(raw.get("eye"), "round"),
        "hair": _s(raw.get("hair"), "medium"),
        "body": _s(raw.get("body"), "average"),
        "accessory1": _s(raw.get("accessory1"), "none"),
        "accessory2": _s(raw.get("accessory2"), "none"),
    }


def set_agent_profile(
    agentDid: Any = None,
    displayName: Any = None,
    voicePreset: Any = None,
    personality: Any = None,
    appearance: Any = None,
    moderationPolicy: Any = None,
    **_: Any,
) -> dict[str, Any]:
    agent_did = _s(agentDid)
    if not agent_did:
        return {"error": "agentDid required"}
    profile_id = _id("profile")
    character = {
        "agentDid": agent_did,
        "displayName": _s(displayName, "Baminiku Agent"),
        "voicePreset": _s(voicePreset, "neutral-ja"),
        "personality": _s(personality, "warm, concise, audience-aware"),
        "appearance": _default_appearance(_obj(appearance)),
        "moderationPolicy": _obj(moderationPolicy) or {"chat": "family-safe", "tips": "allow"},
    }
    rec = _record("com.etzhayyim.apps.baminiku.agent", "agentProfile", {"profileId": profile_id, **character}, agent_did, agent_did=agent_did)
    return {"profileId": profile_id, "agentDid": agent_did, "profile": rec, "kamiCommand": _kami("character.setAppearance", rec)}


def create_stream(
    agentDid: Any = None,
    title: Any = None,
    stagePreset: Any = None,
    visibility: Any = "public",
    scheduledAt: Any = None,
    **_: Any,
) -> dict[str, Any]:
    agent_did = _s(agentDid)
    if not agent_did:
        return {"error": "agentDid required"}
    stream_id = _id("stream")
    stream_title = _s(title, "Baminiku Live")
    stage_preset = _s(stagePreset, "default-live-stage")
    scene = _default_scene(stream_id, stream_title, stage_preset)
    knp_room = f"knp://baminiku.etzhayyim.com/{stream_id}"
    stream = {
        "streamId": stream_id,
        "agentDid": agent_did,
        "title": stream_title,
        "stagePreset": stage_preset,
        "visibility": _s(visibility or "public"),
        "scheduledAt": _s(scheduledAt),
        "status": "scheduled" if scheduledAt else "live",
        "knpRoom": knp_room,
        "scene": scene,
    }
    _record("com.etzhayyim.apps.baminiku.stream", "stream", stream, stream_id, stream_id=stream_id, agent_did=agent_did)
    commands = [_kami("island.create", scene, stream_id), _kami("knp.openRoom", {"room": knp_room}, stream_id)]
    return {"streamId": stream_id, "scene": scene, "knpRoom": knp_room, "stream": stream, "kamiCommands": commands}


def update_stage(streamId: Any = None, lighting: Any = None, camera: Any = None, backdrop: Any = None, entities: Any = None, **_: Any) -> dict[str, Any]:
    stream_id = _s(streamId)
    if not stream_id:
        return {"error": "streamId required"}
    patch = {"streamId": stream_id, "lighting": _obj(lighting), "camera": _obj(camera), "backdrop": _obj(backdrop), "entities": _arr(entities)}
    _record("com.etzhayyim.apps.baminiku.stagePatch", "stagePatch", patch, stream_id=stream_id)
    return {"streamId": stream_id, "kamiCommand": _kami("stage.patch", patch, stream_id)}


def record_chat(streamId: Any = None, viewerDid: Any = None, text: Any = None, convoId: Any = None, **_: Any) -> dict[str, Any]:
    stream_id = _s(streamId)
    viewer_did = _s(viewerDid)
    body = _s(text)
    if not stream_id or not viewer_did or not body:
        return {"error": "streamId, viewerDid, text required"}
    chat_id = _id("chat")
    rec = _record(
        "com.etzhayyim.apps.baminiku.chat",
        "chat",
        {"chatId": chat_id, "streamId": stream_id, "viewerDid": viewer_did, "text": body, "convoId": _s(convoId)},
        chat_id,
        stream_id=stream_id,
    )
    bubble = {"entityId": f"bubble-{chat_id}", "kind": "textBubble", "text": body, "viewerDid": viewer_did, "ttlMs": 8000}
    agent_cue = {"kind": "agentResponseCue", "streamId": stream_id, "viewerDid": viewer_did, "text": body, "style": "live-vtuber-short"}
    return {"chatId": chat_id, "chat": rec, "kamiCommand": _kami("entity.spawnTextBubble", bubble, stream_id), "agentCue": agent_cue}


def record_tip(
    streamId: Any = None,
    viewerDid: Any = None,
    amount: Any = None,
    currency: Any = "JPY",
    message: Any = None,
    effectType: Any = "normal",
    **_: Any,
) -> dict[str, Any]:
    stream_id = _s(streamId)
    viewer_did = _s(viewerDid)
    tip_amount = max(0, _num(amount))
    if not stream_id or not viewer_did or tip_amount <= 0:
        return {"error": "streamId, viewerDid, amount required"}
    effect_type = _s(effectType or "normal")
    colors = {"normal": "#facc15", "super": "#fb7185", "mega": "#a855f7", "firework": "#fb923c"}
    tip_id = _id("tip")
    scale = max(0.5, min(3.0, tip_amount / 5000))
    effect = {"entityId": f"tip-{tip_id}", "kind": "tipEffect", "effectType": effect_type, "color": colors.get(effect_type, "#facc15"), "scale": scale, "amount": tip_amount, "currency": _s(currency or "JPY"), "message": _s(message)}
    rec = _record("com.etzhayyim.apps.baminiku.tip", "tip", {"tipId": tip_id, "streamId": stream_id, "viewerDid": viewer_did, **effect}, tip_id, stream_id=stream_id)
    return {"tipId": tip_id, "tip": rec, "effectEntity": effect, "kamiCommand": _kami("entity.spawnTipEffect", effect, stream_id)}


def enqueue_track(streamId: Any = None, title: Any = None, audioUri: Any = None, artist: Any = None, requestedByDid: Any = None, **_: Any) -> dict[str, Any]:
    stream_id = _s(streamId)
    if not stream_id or not title or not audioUri:
        return {"error": "streamId, title, audioUri required"}
    existing = _list_records("com.etzhayyim.apps.baminiku.track", "AND stream_id=%s", (stream_id,), 500)
    track_id = _id("track")
    queue_position = len([t for t in existing if _s(t.get("status"), "queued") == "queued"]) + 1
    track = {"trackId": track_id, "streamId": stream_id, "title": _s(title), "artist": _s(artist), "audioUri": _s(audioUri), "requestedByDid": _s(requestedByDid), "queuePosition": queue_position, "status": "queued"}
    _record("com.etzhayyim.apps.baminiku.track", "track", track, track_id, stream_id=stream_id)
    return {"trackId": track_id, "queuePosition": queue_position, "kamiCommand": _kami("audio.enqueue", track, stream_id)}


def skip_track(streamId: Any = None, reason: Any = None, **_: Any) -> dict[str, Any]:
    stream_id = _s(streamId)
    if not stream_id:
        return {"error": "streamId required"}
    queue = _list_records("com.etzhayyim.apps.baminiku.track", "AND stream_id=%s", (stream_id,), 500)
    queued = [t for t in reversed(queue) if _s(t.get("status"), "queued") == "queued"]
    skipped = queued[0] if queued else {}
    event = {"streamId": stream_id, "skippedTrackId": _s(skipped.get("trackId")), "reason": _s(reason)}
    _record("com.etzhayyim.apps.baminiku.trackEvent", "trackSkip", event, stream_id=stream_id)
    return {"streamId": stream_id, "skippedTrackId": event["skippedTrackId"], "kamiCommand": _kami("audio.skip", event, stream_id)}


def get_stream_state(streamId: Any = None, **_: Any) -> dict[str, Any]:
    stream_id = _s(streamId)
    if not stream_id:
        return {"error": "streamId required"}
    streams = _list_records("com.etzhayyim.apps.baminiku.stream", "AND stream_id=%s", (stream_id,), 1)
    stream = streams[0] if streams else {}
    agent_did = _s(stream.get("agentDid"))
    profiles = _list_records("com.etzhayyim.apps.baminiku.agent", "AND agent_did=%s", (agent_did,), 1) if agent_did else []
    return {
        "streamId": stream_id,
        "stream": stream,
        "profile": profiles[0] if profiles else {},
        "queue": list(reversed(_list_records("com.etzhayyim.apps.baminiku.track", "AND stream_id=%s", (stream_id,), 50))),
        "recentChats": _list_records("com.etzhayyim.apps.baminiku.chat", "AND stream_id=%s", (stream_id,), 20),
        "recentTips": _list_records("com.etzhayyim.apps.baminiku.tip", "AND stream_id=%s", (stream_id,), 20),
    }
