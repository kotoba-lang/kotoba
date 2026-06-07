"""Arms registry business logic for Zeebe workers."""

from __future__ import annotations

import hashlib
import secrets
import string
import time
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

APP_HANDLE = "arms.etzhayyim.com"
PRIMARY_DID = "did:web:arms.etzhayyim.com"

VALID_CATEGORIES = {
    "pistol", "revolver", "rifle", "carbine", "shotgun", "smg", "hmg", "lmg",
    "sniper_rifle", "anti_material_rifle", "rocket_launcher", "grenade_launcher",
    "mortar", "other_small_arms", "other_military",
}
VALID_PERMIT_TYPES = {"acquisition", "possession", "carry", "military", "law_enforcement", "export", "research"}
VALID_INCIDENT_TYPES = {"theft", "loss", "unauthorized_discharge", "export_violation", "tampering"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def nanoid(length: int = 12) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def sha256hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _caller(args: dict[str, Any]) -> str:
    return str(args.get("callerDid") or args.get("primaryDid") or PRIMARY_DID)


def _err(error: str, message: str, status: int = 400) -> dict[str, Any]:
    return {"ok": False, "error": error, "message": message, "status": status}


def register_firearm(**args: Any) -> dict[str, Any]:
    serial = args.get("serialNumber")
    make = args.get("make")
    model = args.get("model")
    caliber = args.get("caliber")
    category = args.get("category")
    if not isinstance(serial, str) or len(serial) < 4:
        return _err("InvalidRequest", "serialNumber required (min 4 chars)")
    if not make:
        return _err("InvalidRequest", "make required")
    if not model:
        return _err("InvalidRequest", "model required")
    if not caliber:
        return _err("InvalidRequest", "caliber required")
    if category not in VALID_CATEGORIES:
        return _err("InvalidRequest", f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}")
    caller = _caller(args)
    holder = str(args.get("registrantDid") or caller)
    serial_hash = sha256hex(serial)
    rid = nanoid(10)
    firearm_vid = f"at://did:web:{APP_HANDLE}/com.etzhayyim.apps.arms.firearm/{rid}"
    pii_vid = f"at://did:web:{APP_HANDLE}/com.etzhayyim.apps.arms.firearmPii/{rid}"
    created = datetime.now(timezone.utc)
    get_kotoba_client().insert_row(
        "vertex_arms_firearm",
        {
            "vertex_id": firearm_vid,
            "created_date": created.strftime("%Y-%m-%d"),
            "sensitivity_ord": 2,
            "owner_did": holder,
            "serial_number_hash": serial_hash,
            "make": make,
            "model": model,
            "caliber": caliber,
            "category": category,
            "status": "active",
            "registered_at": created.isoformat(),
            "created_at": created.isoformat(),
            "org_id": holder,
            "user_id": caller,
            "actor_id": f"arms.{category}",
        },
    )
    get_kotoba_client().insert_row(
        "vertex_arms_firearm_pii",
        {
            "vertex_id": pii_vid,
            "firearm_vid": firearm_vid,
            "serial_number": serial,
            "manufacturer_code": make,
            "country_of_origin": args.get("countryOfOrigin"),
            "year_of_manufacture": args.get("yearOfManufacture"),
            "created_at": created.isoformat(),
            "org_id": holder,
            "user_id": caller,
            "actor_id": f"arms.{category}",
        },
    )
    get_kotoba_client().insert_row(
        "edge_arms_firearm_to_holder",
        {
            "src": firearm_vid,
            "dst": holder,
            "rel": "held_by",
            "since": created.isoformat(),
            "permit_vid": None,
        },
    )
    return {"ok": True, "firearmVid": firearm_vid, "serialHash": serial_hash, "make": make, "model": model, "caliber": caliber, "category": category, "status": "active", "registeredAt": created.isoformat()}


def authenticate_holder(**args: Any) -> dict[str, Any]:
    firearm_vid = args.get("firearmVid")
    holder = args.get("holderDid")
    if not isinstance(firearm_vid, str):
        return _err("InvalidRequest", "firearmVid required")
    if not isinstance(holder, str):
        return _err("InvalidRequest", "holderDid required")
    firearm = get_kotoba_client().select_first_where(
        "vertex_arms_firearm", "vertex_id", firearm_vid, columns=["status"]
    )
    if not firearm:
        return _err("NotFound", "firearm not found", 404)
    if firearm["status"] in {"stolen", "lost"}:
        return _err("FirearmUnavailable", f"firearm status is {firearm['status']}", 409)

    permit = get_kotoba_client().select_first_where(
        "vertex_arms_permit",
        "holder_did",
        holder,
        columns=["vertex_id"],
        # R0: Multi-predicate filter applied in-Python
    )
    if not permit or not (
        permit["status"] == "active" if "status" in permit else False
    ):
        return _err("PermitRequired", "no active permit found for holder", 403)

    challenge = nanoid(32)
    session_id = nanoid(12)
    session_vid = f"at://did:web:{APP_HANDLE}/com.etzhayyim.apps.arms.authSession/{session_id}"
    initiated = datetime.now(timezone.utc)
    get_kotoba_client().insert_row(
        "vertex_arms_auth_session",
        {
            "vertex_id": session_vid,
            "created_date": initiated.strftime("%Y-%m-%d"),
            "sensitivity_ord": 2,
            "owner_did": holder,
            "firearm_vid": firearm_vid,
            "holder_did": holder,
            "challenge": sha256hex(challenge),
            "response_hash": None,
            "auth_status": "pending",
            "initiated_at": initiated.isoformat(),
            "completed_at": None,
            "created_at": initiated.isoformat(),
            "org_id": holder,
            "user_id": _caller(args),
            "actor_id": "arms.auth",
        },
    )
    return {"ok": True, "sessionVid": session_vid, "challenge": challenge, "holderDid": holder, "firearmVid": firearm_vid, "expiresIn": 300, "instructions": "Sign challenge with your DID private key and submit to verifyAuthChallenge"}


def verify_auth_challenge(**args: Any) -> dict[str, Any]:
    session_vid = args.get("sessionVid")
    signature = args.get("signatureHex")
    if not isinstance(session_vid, str):
        return _err("InvalidRequest", "sessionVid required")
    if not isinstance(signature, str):
        return _err("InvalidRequest", "signatureHex required")
    session = _fetch_one("SELECT auth_status, initiated_at, holder_did, firearm_vid FROM vertex_arms_auth_session WHERE vertex_id = %s LIMIT 1", (session_vid,))
    if not session:
        return _err("NotFound", "auth session not found", 404)
    if session[0] != "pending":
        return _err("SessionExpired", f"session status is {session[0]}", 409)
    completed = now_iso()
    try:
        age = time.time() - time.mktime(time.strptime(str(session[1]).replace("Z", "UTC"), "%Y-%m-%dT%H:%M:%S%Z"))
    except Exception:
        age = 0
    if age > 300:
        _execute("UPDATE vertex_arms_auth_session SET auth_status = 'expired', completed_at = %s WHERE vertex_id = %s", (completed, session_vid))
        return _err("SessionExpired", "auth challenge expired (>5 min)", 409)
    _execute(
        "UPDATE vertex_arms_auth_session SET auth_status = 'passed', response_hash = %s, completed_at = %s WHERE vertex_id = %s",
        (sha256hex(signature), completed, session_vid),
    )
    return {"ok": True, "sessionVid": session_vid, "authStatus": "passed", "completedAt": completed, "holderDid": session[2], "firearmVid": session[3]}


def issue_permit(**args: Any) -> dict[str, Any]:
    holder = args.get("holderDid")
    permit_type = args.get("permitType")
    category = args.get("categoryAllowed")
    permit_number = args.get("permitNumber")
    if not isinstance(holder, str):
        return _err("InvalidRequest", "holderDid required")
    if permit_type not in VALID_PERMIT_TYPES:
        return _err("InvalidRequest", f"permitType must be one of: {', '.join(sorted(VALID_PERMIT_TYPES))}")
    if not isinstance(category, str):
        return _err("InvalidRequest", "categoryAllowed required")
    if not isinstance(permit_number, str) or len(permit_number) < 4:
        return _err("InvalidRequest", "permitNumber required (min 4 chars)")
    caller = _caller(args)
    permit_hash = sha256hex(permit_number)
    rid = nanoid(10)
    permit_vid = f"at://did:web:{APP_HANDLE}/com.etzhayyim.apps.arms.permit/{rid}"
    pii_vid = f"at://did:web:{APP_HANDLE}/com.etzhayyim.apps.arms.permitPii/{rid}"
    issued = now_iso()
    _execute(
        """
        INSERT INTO vertex_arms_permit
          (vertex_id, created_date, sensitivity_ord, owner_did, holder_did, permit_type,
           permit_number_hash, category_allowed, issuer_did, issued_at, expires_at, status,
           created_at, org_id, user_id, actor_id)
        VALUES (%s, %s, 2, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, %s, 'arms.permit')
        """,
        (permit_vid, issued[:10], holder, holder, permit_type, permit_hash, category, caller, issued, args.get("expiresAt"), issued, holder, caller),
    )
    _execute(
        "INSERT INTO vertex_arms_permit_pii (vertex_id, permit_vid, permit_number, created_at, org_id, user_id, actor_id) VALUES (%s, %s, %s, %s, %s, %s, 'arms.permit')",
        (pii_vid, permit_vid, permit_number, issued, holder, caller),
    )
    return {"ok": True, "permitVid": permit_vid, "permitHash": permit_hash, "holderDid": holder, "permitType": permit_type, "categoryAllowed": category, "status": "active", "issuedAt": issued}


def _passed_session(session_vid: str, holder: str, firearm_vid: str | None = None) -> tuple[Any, ...] | None:
    if firearm_vid:
        return _fetch_one("SELECT vertex_id FROM vertex_arms_auth_session WHERE vertex_id = %s AND holder_did = %s AND firearm_vid = %s AND auth_status = 'passed' LIMIT 1", (session_vid, holder, firearm_vid))
    return _fetch_one("SELECT vertex_id FROM vertex_arms_auth_session WHERE vertex_id = %s AND holder_did = %s AND auth_status = 'passed' LIMIT 1", (session_vid, holder))


def transfer_custody(**args: Any) -> dict[str, Any]:
    firearm_vid, from_holder, to_holder, session_vid = args.get("firearmVid"), args.get("fromHolderDid"), args.get("toHolderDid"), args.get("authSessionVid")
    if not all(isinstance(v, str) for v in (firearm_vid, from_holder, to_holder, session_vid)):
        return _err("InvalidRequest", "firearmVid/fromHolderDid/toHolderDid/authSessionVid required")
    if not _passed_session(session_vid, from_holder):
        return _err("AuthRequired", "valid passed auth session required", 403)
    permit_vid = args.get("permitVid")
    if permit_vid and not _fetch_one("SELECT vertex_id FROM vertex_arms_permit WHERE vertex_id = %s AND holder_did = %s AND status = 'active' LIMIT 1", (permit_vid, to_holder)):
        return _err("PermitNotFound", "toHolder permit not found or inactive", 404)
    occurred = now_iso()
    event_vid = f"at://did:web:{APP_HANDLE}/com.etzhayyim.apps.arms.custodyEvent/{nanoid(10)}"
    _custody_event(event_vid, from_holder, firearm_vid, "transfer", from_holder, to_holder, session_vid, permit_vid, args.get("locationCode"), None, occurred, _caller(args))
    _execute("DELETE FROM edge_arms_firearm_to_holder WHERE src = %s", (firearm_vid,))
    _execute("INSERT INTO edge_arms_firearm_to_holder (src, dst, rel, since, permit_vid) VALUES (%s, %s, 'held_by', %s, %s)", (firearm_vid, to_holder, occurred, permit_vid))
    if permit_vid:
        _execute("DELETE FROM edge_arms_firearm_to_permit WHERE src = %s", (firearm_vid,))
        _execute("INSERT INTO edge_arms_firearm_to_permit (src, dst, rel) VALUES (%s, %s, 'covered_by')", (firearm_vid, permit_vid))
    return {"ok": True, "eventVid": event_vid, "firearmVid": firearm_vid, "fromHolderDid": from_holder, "toHolderDid": to_holder, "occurredAt": occurred}


def _custody_event(event_vid: str, owner: str, firearm_vid: str, event_type: str, from_holder: str | None, to_holder: str | None, session_vid: str | None, permit_vid: str | None, location: Any, notes: Any, occurred: str, caller: str, sensitivity: int = 2) -> None:
    _execute(
        """
        INSERT INTO vertex_arms_custody_event
          (vertex_id, created_date, sensitivity_ord, owner_did, firearm_vid, event_type,
           from_holder_did, to_holder_did, auth_session_vid, permit_vid, location_code,
           notes, occurred_at, created_at, org_id, user_id, actor_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (event_vid, occurred[:10], sensitivity, owner, firearm_vid, event_type, from_holder, to_holder, session_vid, permit_vid, location, notes, occurred, occurred, owner, caller, "arms.incident" if sensitivity == 3 else "arms.custody"),
    )


def check_out_firearm(**args: Any) -> dict[str, Any]:
    firearm_vid, holder, session_vid = args.get("firearmVid"), args.get("holderDid"), args.get("authSessionVid")
    if not all(isinstance(v, str) for v in (firearm_vid, holder, session_vid)):
        return _err("InvalidRequest", "firearmVid/holderDid/authSessionVid required")
    firearm = _fetch_one("SELECT status FROM vertex_arms_firearm WHERE vertex_id = %s LIMIT 1", (firearm_vid,))
    if not firearm:
        return _err("NotFound", "firearm not found", 404)
    if not _passed_session(session_vid, holder, firearm_vid):
        return _err("AuthRequired", "passed auth session for this holder+firearm required", 403)
    if firearm[0] != "active":
        return _err("FirearmUnavailable", f"firearm status is {firearm[0]}", 409)
    occurred = now_iso()
    event_vid = f"at://did:web:{APP_HANDLE}/com.etzhayyim.apps.arms.custodyEvent/{nanoid(10)}"
    _custody_event(event_vid, holder, firearm_vid, "check_out", holder, None, session_vid, None, args.get("locationCode"), None, occurred, _caller(args))
    _execute("UPDATE vertex_arms_firearm SET status = 'checked_out' WHERE vertex_id = %s", (firearm_vid,))
    return {"ok": True, "eventVid": event_vid, "firearmVid": firearm_vid, "holderDid": holder, "status": "checked_out", "occurredAt": occurred}


def check_in_firearm(**args: Any) -> dict[str, Any]:
    firearm_vid, holder = args.get("firearmVid"), args.get("holderDid")
    if not isinstance(firearm_vid, str) or not isinstance(holder, str):
        return _err("InvalidRequest", "firearmVid/holderDid required")
    firearm = _fetch_one("SELECT status FROM vertex_arms_firearm WHERE vertex_id = %s LIMIT 1", (firearm_vid,))
    if not firearm:
        return _err("NotFound", "firearm not found", 404)
    if firearm[0] != "checked_out":
        return _err("InvalidRequest", f"firearm is not checked out (status: {firearm[0]})", 409)
    occurred = now_iso()
    event_vid = f"at://did:web:{APP_HANDLE}/com.etzhayyim.apps.arms.custodyEvent/{nanoid(10)}"
    _custody_event(event_vid, holder, firearm_vid, "check_in", None, holder, None, None, args.get("locationCode"), args.get("notes"), occurred, _caller(args))
    _execute("UPDATE vertex_arms_firearm SET status = 'active' WHERE vertex_id = %s", (firearm_vid,))
    return {"ok": True, "eventVid": event_vid, "firearmVid": firearm_vid, "holderDid": holder, "status": "active", "occurredAt": occurred}


def report_incident(**args: Any) -> dict[str, Any]:
    firearm_vid, incident = args.get("firearmVid"), args.get("incidentType")
    if not isinstance(firearm_vid, str):
        return _err("InvalidRequest", "firearmVid required")
    if incident not in VALID_INCIDENT_TYPES:
        return _err("InvalidRequest", f"incidentType must be one of: {', '.join(sorted(VALID_INCIDENT_TYPES))}")
    firearm = _fetch_one("SELECT status FROM vertex_arms_firearm WHERE vertex_id = %s LIMIT 1", (firearm_vid,))
    if not firearm:
        return _err("NotFound", "firearm not found", 404)
    caller = _caller(args)
    new_status = "stolen" if incident == "theft" else "lost" if incident == "loss" else firearm[0]
    event_type = "reported_stolen" if incident == "theft" else "reported_lost" if incident == "loss" else "check_out"
    occurred = now_iso()
    event_vid = f"at://did:web:{APP_HANDLE}/com.etzhayyim.apps.arms.custodyEvent/{nanoid(10)}"
    defence_vid = f"at://did:web:arms.etzhayyim.com/com.etzhayyim.apps.arms.incident/{nanoid(12)}"
    _custody_event(event_vid, caller, firearm_vid, event_type, caller, None, None, None, args.get("locationCode"), args.get("description"), occurred, caller, 3)
    _execute(
        """
        INSERT INTO vertex_open_defence_event
          (vertex_id, owner_did, bpmn_process_id, nsid, project, subject_vid, action_class,
           severity, detected_at, created_at, sensitivity_ord, org_id, user_id, actor_id)
        VALUES (%s, %s, 'arms_report_incident', 'com.etzhayyim.apps.arms.reportIncident', 'arms', %s, %s, %s, %s, %s, 3, %s, %s, 'arms.incident')
        """,
        (defence_vid, caller, firearm_vid, f"arms.{incident}", "critical" if incident in {"theft", "unauthorized_discharge"} else "high", occurred, occurred, caller, caller),
    )
    if new_status != firearm[0]:
        _execute("UPDATE vertex_arms_firearm SET status = %s WHERE vertex_id = %s", (new_status, firearm_vid))
    return {"ok": True, "eventVid": event_vid, "defenceEventVid": defence_vid, "firearmVid": firearm_vid, "incidentType": incident, "newStatus": new_status, "occurredAt": occurred}


def get_firearm(**args: Any) -> dict[str, Any]:
    serial_hash, firearm_vid = args.get("serialHash"), args.get("firearmVid")
    if not serial_hash and not firearm_vid:
        return _err("InvalidRequest", "serialHash or firearmVid required")
    if firearm_vid:
        row = _fetch_one("SELECT vertex_id, owner_did, serial_number_hash, make, model, caliber, category, status, registered_at FROM vertex_arms_firearm WHERE vertex_id = %s LIMIT 1", (firearm_vid,))
    else:
        row = _fetch_one("SELECT vertex_id, owner_did, serial_number_hash, make, model, caliber, category, status, registered_at FROM vertex_arms_firearm WHERE serial_number_hash = %s LIMIT 1", (serial_hash,))
    if not row:
        return _err("NotFound", "firearm not found", 404)
    holder = _fetch_one("SELECT dst FROM edge_arms_firearm_to_holder WHERE src = %s LIMIT 1", (row[0],))
    return {"ok": True, "vertex_id": row[0], "owner_did": row[1], "serial_number_hash": row[2], "make": row[3], "model": row[4], "caliber": row[5], "category": row[6], "status": row[7], "registered_at": row[8], "currentHolderDid": holder[0] if holder else None}


def list_firearms(**args: Any) -> dict[str, Any]:
    limit = min(500, max(1, int(args.get("limit") or 100)))
    offset = max(0, int(args.get("offset") or 0))
    where: list[str] = []
    params: list[Any] = []
    for key, col in (("status", "status"), ("category", "category")):
        if args.get(key):
            where.append(f"{col} = %s")
            params.append(args[key])
    if args.get("holderDid"):
        where.append("vertex_id IN (SELECT src FROM edge_arms_firearm_to_holder WHERE dst = %s)")
        params.append(args["holderDid"])
    sql = "SELECT vertex_id, owner_did, make, model, caliber, category, status, registered_at FROM vertex_arms_firearm"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY registered_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    rows = _fetch_all(sql, tuple(params))
    return {"ok": True, "firearms": [dict(zip(["vertex_id", "owner_did", "make", "model", "caliber", "category", "status", "registered_at"], r)) for r in rows], "limit": limit, "offset": offset}


def list_permits(**args: Any) -> dict[str, Any]:
    holder = args.get("holderDid")
    if not holder:
        return _err("InvalidRequest", "holderDid required")
    limit = min(200, max(1, int(args.get("limit") or 50)))
    offset = max(0, int(args.get("offset") or 0))
    where = ["holder_did = %s"]
    params: list[Any] = [holder]
    for key, col in (("permitType", "permit_type"), ("status", "status")):
        if args.get(key):
            where.append(f"{col} = %s")
            params.append(args[key])
    params.extend([limit, offset])
    rows = _fetch_all(
        f"SELECT vertex_id, holder_did, permit_type, permit_number_hash, category_allowed, issuer_did, issued_at, expires_at, status FROM vertex_arms_permit WHERE {' AND '.join(where)} ORDER BY issued_at DESC LIMIT %s OFFSET %s",
        tuple(params),
    )
    return {"ok": True, "permits": [dict(zip(["vertex_id", "holder_did", "permit_type", "permit_number_hash", "category_allowed", "issuer_did", "issued_at", "expires_at", "status"], r)) for r in rows], "limit": limit, "offset": offset}


def get_audit_log(**args: Any) -> dict[str, Any]:
    firearm_vid = args.get("firearmVid")
    if not firearm_vid:
        return _err("InvalidRequest", "firearmVid required")
    limit = min(500, max(1, int(args.get("limit") or 100)))
    offset = max(0, int(args.get("offset") or 0))
    rows = _fetch_all(
        "SELECT vertex_id, event_type, from_holder_did, to_holder_did, auth_session_vid, permit_vid, location_code, notes, occurred_at FROM vertex_arms_custody_event WHERE firearm_vid = %s ORDER BY occurred_at ASC LIMIT %s OFFSET %s",
        (firearm_vid, limit, offset),
    )
    return {"ok": True, "firearmVid": firearm_vid, "events": [dict(zip(["vertex_id", "event_type", "from_holder_did", "to_holder_did", "auth_session_vid", "permit_vid", "location_code", "notes", "occurred_at"], r)) for r in rows], "limit": limit, "offset": offset}
