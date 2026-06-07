"""Demining AppView handlers for BPMN + Zeebe.

Cloudflare Worker stays a thin edge facade. Humanitarian Mine Action domain
rules, Tier 3 field handling, and graph writes live here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:dm1nactz.etzhayyim.com"
PROHIBITED_PATTERNS = ("produce_apm", "stockpile_apm", "transfer_apm", "deploy_apm", "manufacture_apm")
TIER3_FIELDS = {"geometryWkt", "hitCoordsWkt", "operatorDid", "operatorDids", "victimRef"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _ctx_did(kwargs: dict[str, Any], fallback: str = OWNER_DID) -> str:
    for key in ("did", "callerDid", "actorDid", "ownerDid"):
        value = kwargs.get(key)
        if isinstance(value, str) and value:
            return value
    caller = kwargs.get("caller")
    if isinstance(caller, dict):
        did = caller.get("did")
        if isinstance(did, str) and did:
            return did
    return fallback


def _reject_prohibited(record: dict[str, Any]) -> str | None:
    text = json.dumps(record, ensure_ascii=False, sort_keys=True).lower()
    for pattern in PROHIBITED_PATTERNS:
        if pattern in text:
            return f"prohibited activity in record: {pattern}"
    return None


def _split_tier3(input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    public: dict[str, Any] = {}
    tier3: dict[str, Any] = {}
    for key, value in input.items():
        if key in TIER3_FIELDS:
            tier3[key] = value
        else:
            public[key] = value
    return public, tier3





def _write_public(owner: str, record_type: str, record_id: str, collection: str, rec: dict[str, Any], tier: int) -> None:
    vertex_id = f"at://{owner}/{collection}/{record_id}"
    get_kotoba_client().insert_row(
        "vertex_atrecord_demining_public",
        {
            "vertex_id": vertex_id,
            "owner_did": owner,
            "record_type": record_type,
            "record_id": record_id,
            "collection": collection,
            "record_json": json.dumps(rec, ensure_ascii=False, sort_keys=True),
            "sensitivity_tier": tier,
            "created_at": now_iso(),
        },
    )


def _audit(actor: str, action: str, record_id: str = "", record_type: str = "", field_name: str = "", jurisdiction: str = "", reason: str = "") -> None:
    get_kotoba_client().insert_row(
        "vertex_atrecord_demining_tier3_audit",
        {
            "vertex_id": _id("audit"),
            "occurred_at": now_iso(),
            "actor_did": actor,
            "action": action,
            "record_id": record_id or None,
            "record_type": record_type or None,
            "field_name": field_name or None,
            "jurisdiction": jurisdiction or None,
            "reason": reason or None,
        },
    )


def _store_tier3(record_id: str, record_type: str, owner: str, jurisdiction: str | None, actor: str, fields: dict[str, Any]) -> dict[str, list[str]]:
    stored: list[str] = []
    skipped: list[str] = []
    for field, value in fields.items():
        if value is None or value == "":
            skipped.append(field)
            continue
        value_text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
        vertex_id = f"demining:tier3:{record_id}:{field}"
        get_kotoba_client().insert_row(
            "vertex_atrecord_demining_tier3_field",
            {
                "vertex_id": vertex_id,
                "owner_did": owner,
                "record_id": record_id,
                "record_type": record_type,
                "field_name": field,
                "field_value": value_text,
                "jurisdiction": jurisdiction,
                "actor_did": actor,
                "released": False,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
        )
        stored.append(field)
        _audit(actor, "write", record_id, record_type, field, jurisdiction or "")
    return {"stored": stored, "skipped": skipped}


def _load_tier3(record_id: str, field: str, actor: str) -> str | None:
    client = get_kotoba_client()
    rows = client.select_where(
        "vertex_atrecord_demining_tier3_field",
        "record_id",
        record_id,
        columns=["field_value", "record_type", "jurisdiction", "_seq"], # include _seq for sorting
        limit=2000 # R0: arbitrary limit, filtering in python
    )
    # R0: Order by _seq in Python to emulate ORDER BY _seq DESC LIMIT 1
    rows = sorted(rows, key=lambda x: x.get("_seq", 0), reverse=True)
    if not rows:
        return None
    row = rows[0]
    _audit(actor, "read", record_id, str(row.get("record_type") or ""), field, str(row.get("jurisdiction") or ""))
    value = row.get("field_value")
    return str(value) if value is not None else None


def _mark_released(area_id: str, decision_id: str, actor: str) -> None:
    # R0: Multi-row update by fetching and re-inserting
    client = get_kotoba_client()
    existing_records = client.select_where(
        "vertex_atrecord_demining_tier3_field",
        "record_id",
        area_id,
        limit=2000 # R0: arbitrary limit for records to update
    )
    for record in existing_records:
        record["released"] = True
        record["released_at"] = now_iso()
        record["released_by_decision"] = decision_id
        record["updated_at"] = now_iso()
        client.insert_row("vertex_atrecord_demining_tier3_field", record)
    _audit(actor, "release", area_id, "hazardArea", reason=f"decision={decision_id}")


def register_hazard_area(**kwargs: Any) -> dict[str, Any]:
    reject = _reject_prohibited(kwargs)
    if reject:
        return {"error": reject}
    area_id = _id("area")
    actor = _ctx_did(kwargs)
    owner = str(kwargs.get("ownerDid") or actor)
    public, tier3 = _split_tier3(kwargs)
    res = _store_tier3(area_id, "hazardArea", owner, kwargs.get("jurisdiction"), actor, tier3)
    rec = {**public, "areaId": area_id, "tier": 3, "createdAt": now_iso()}
    _write_public(owner, "hazardArea", area_id, "com.etzhayyim.apps.demining.hazardArea", rec, 3)
    return {"areaId": area_id, "tier": 3, "tier3Stored": res["stored"], "tier3Skipped": res["skipped"]}


def list_hazard_areas(status: Any = None, adminAreaDid: Any = None, contaminationType: Any = None, offset: Any = 0, limit: Any = 50, **_: Any) -> dict[str, Any]:
    lim = max(1, min(int(limit or 50), 200))
    off = max(0, int(offset or 0))
    client = get_kotoba_client()
    rows = client.select_where(
        "vertex_atrecord_demining_public",
        "record_type",
        "hazardArea",
        columns=["record_id", "owner_did", "record_json", "created_at", "_seq"], # Include _seq for sorting
        limit=2000 # R0: arbitrary limit, filtering in python
    )
    # R0: Order by _seq in Python to emulate ORDER BY _seq DESC
    rows = sorted(rows, key=lambda x: x.get("_seq", 0), reverse=True)
    areas: list[dict[str, Any]] = []
    for row in rows:
        try:
            rec = json.loads(str(row.get("record_json") or "{}"))
        except json.JSONDecodeError:
            rec = {"areaId": row.get("record_id")}
        if status and rec.get("status") != status:
            continue
        if adminAreaDid and rec.get("adminAreaDid") != adminAreaDid:
            continue
        if contaminationType:
            types = rec.get("contaminationTypes") if isinstance(rec.get("contaminationTypes"), list) else []
            if contaminationType not in types:
                continue
        rec.pop("geometryWkt", None)
        areas.append(rec)
    total = len(areas)
    return {
        "areas": areas[off : off + lim],
        "total": total,
        "offset": off,
        "limit": lim,
        "note": "Geometry omitted. Tier 3 access requires demining.viewCoordinates capability.",
    }


def record_detection(**kwargs: Any) -> dict[str, Any]:
    reject = _reject_prohibited(kwargs)
    if reject:
        return {"error": reject}
    detection_id = _id("det")
    actor = _ctx_did(kwargs)
    owner = str(kwargs.get("operatorDid") or actor)
    public, tier3 = _split_tier3(kwargs)
    _store_tier3(detection_id, "detectionEvent", owner, kwargs.get("jurisdiction"), actor, tier3)
    _write_public(owner, "detectionEvent", detection_id, "com.etzhayyim.apps.demining.detectionEvent", {**public, "detectionId": detection_id, "tier": 3, "createdAt": now_iso()}, 3)
    return {"detectionId": detection_id}


def record_clearance_task(**kwargs: Any) -> dict[str, Any]:
    reject = _reject_prohibited(kwargs)
    if reject:
        return {"error": reject}
    task_id = str(kwargs.get("taskId") or _id("task"))
    actor = _ctx_did(kwargs)
    public, tier3 = _split_tier3(kwargs)
    _store_tier3(task_id, "clearanceTask", actor, kwargs.get("jurisdiction"), actor, tier3)
    _write_public(actor, "clearanceTask", task_id, "com.etzhayyim.apps.demining.clearanceTask", {**public, "taskId": task_id, "tier": 2, "createdAt": now_iso()}, 2)
    return {"taskId": task_id}


def release_area(**kwargs: Any) -> dict[str, Any]:
    reject = _reject_prohibited(kwargs)
    if reject:
        return {"error": reject}
    area_id = str(kwargs.get("areaId") or "")
    if not area_id:
        return {"error": "areaId required"}
    actor = _ctx_did(kwargs)
    decision_id = _id("rel")
    stored = _load_tier3(area_id, "geometryWkt", actor)
    polygon_public = kwargs.get("polygonPublic") or stored
    _mark_released(area_id, decision_id, actor)
    rec = {**kwargs, "decisionId": decision_id, "areaId": area_id, "polygonPublic": polygon_public, "tier": 1, "decidedAt": kwargs.get("decidedAt") or now_iso()}
    _write_public(actor, "landReleaseDecision", decision_id, "com.etzhayyim.apps.demining.landReleaseDecision", rec, 1)
    return {"decisionId": decision_id, "tier": 1, "polygonPublished": bool(polygon_public)}


def record_eore_session(**kwargs: Any) -> dict[str, Any]:
    session_id = str(kwargs.get("sessionId") or _id("eore"))
    actor = _ctx_did(kwargs)
    rec = {**kwargs, "sessionId": session_id, "tier": 1, "createdAt": now_iso()}
    _write_public(actor, "eoreSession", session_id, "com.etzhayyim.apps.demining.eoreSession", rec, 1)
    return {"sessionId": session_id}


def record_victim(**kwargs: Any) -> dict[str, Any]:
    reject = _reject_prohibited(kwargs)
    if reject:
        return {"error": reject}
    record_id = _id("victim")
    actor = _ctx_did(kwargs)
    public, tier3 = _split_tier3(kwargs)
    _store_tier3(record_id, "victimRecord", actor, kwargs.get("jurisdiction"), actor, tier3)
    _write_public(actor, "victimRecord", record_id, "com.etzhayyim.apps.demining.victimRecord", {**public, "recordId": record_id, "tier": 3, "createdAt": now_iso()}, 3)
    return {"recordId": record_id}
