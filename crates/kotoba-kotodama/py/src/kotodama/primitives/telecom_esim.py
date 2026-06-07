"""telecom Phase 18 primitives — eSIM / eUICC Lifecycle (GSMA SGP.22 / SGP.02).

Eight BPMN service tasks:

  - telecom.esim.euicc.provision   EID registration
  - telecom.esim.profile.download  SM-DP+ profile download
  - telecom.esim.profile.enable    SGP.22 §3.2 enable
  - telecom.esim.profile.disable   SGP.22 §3.2 disable
  - telecom.esim.profile.delete    SGP.22 §3.3 delete
  - telecom.esim.smds.register     SM-DS event registration (SGP.22 §3.6)
  - telecom.esim.euicc.audit       eUICC state snapshot
  - telecom.esim.profile.transfer  MNO-to-MNO ownership transfer

PII discipline:
  eid  → sha256: hashed (device-bound, quasi-PII)
  iccid → sha256: hashed (quasi-PII)
  sensitivity_ord = 2 for all tables
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.esim"

DEVICE_KINDS = {"smartphone", "tablet", "wearable", "iot", "automotive", "cpe"}
PROFILE_TYPES = {"telecom", "iot", "m2m", "enterprise"}
PROFILE_STATES = {"downloaded", "installed", "enabled", "disabled", "deleted"}
OP_KINDS = {"enable", "disable", "delete"}
DISABLE_REASONS = {"suspended", "lostDevice", "fraudPrevention", "maintenanceMode", "userRequest"}
DELETE_REASONS = {"contractTerminated", "deviceReplaced", "mnoMigration", "euiccReset", "userRequest"}
EVENT_TYPES = {"profileDownload", "profileUpdate", "policyUpdate"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _new_id(prefix: str, *parts: Any) -> str:
    if parts:
        digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:24]
        return f"{prefix}_{digest}"
    return f"{prefix}_{secrets.token_hex(10)}"


def _vid(kind: str, key: str) -> str:
    return f"at://{TELECOM_DID}/com.etzhayyim.apps.telecom.{kind}/{key}"


def _hash(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("sha256:"):
        return value
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _require(payload: dict[str, Any], fields: list[str]) -> None:
    missing = [f for f in fields if payload.get(f) in (None, "")]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


# ─── provisionEuicc ──────────────────────────────────────────────────────────

def handle_provision_euicc(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["eid", "deviceKind"])

    eid_hash = _hash(payload["eid"])
    device_kind = payload["deviceKind"]
    if device_kind not in DEVICE_KINDS:
        device_kind = "smartphone"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("euicc", _new_id("euicc", eid_hash))

    get_kotoba_client().insert_row("vertex_telecom_esim_euicc", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "eid": eid_hash,
        "device_kind": device_kind,
        "manufacturer_name": payload.get('manufacturerName'),
        "platform_version": payload.get('platformVersion'),
        "smdp_address": payload.get('smdpAddress'),
        "smds_address": payload.get('smdsAddress'),
        "profile_slots": payload.get('profileSlots'),
        "observed_at": observed_at,
        "status": 'active',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "eid": eid_hash, "status": "active"}


# ─── downloadEsimProfile ─────────────────────────────────────────────────────

def handle_download_esim_profile(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["downloadId", "eid", "iccid", "smdpAddress"])

    eid_hash = _hash(payload["eid"])
    iccid_hash = _hash(payload["iccid"])
    profile_type = payload.get("profileType")
    if profile_type and profile_type not in PROFILE_TYPES:
        profile_type = "telecom"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("esimProfile", payload["downloadId"])

    get_kotoba_client().insert_row("vertex_telecom_esim_profile", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "download_id": payload['downloadId'],
        "eid": eid_hash,
        "iccid": iccid_hash,
        "matching_id": payload.get('matchingId'),
        "smdp_address": payload['smdpAddress'],
        "profile_type": profile_type,
        "mno": payload.get('mno'),
        "profile_state": 'installed',
        "observed_at": observed_at,
        "status": 'completed',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "iccid": iccid_hash, "status": "completed"}


# ─── enableEsimProfile ───────────────────────────────────────────────────────

def handle_enable_esim_profile(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["operationId", "eid", "iccid"])

    eid_hash = _hash(payload["eid"])
    iccid_hash = _hash(payload["iccid"])
    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("esimProfileOp", payload["operationId"])

    get_kotoba_client().insert_row("vertex_telecom_esim_profile_op", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "operation_id": payload['operationId'],
        "eid": eid_hash,
        "iccid": iccid_hash,
        "op_kind": 'enable',
        "refresh_flag": payload.get('refreshFlag', False),
        "reason": None,
        "observed_at": observed_at,
        "status": 'enabled',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "iccid": iccid_hash, "status": "enabled"}


# ─── disableEsimProfile ──────────────────────────────────────────────────────

def handle_disable_esim_profile(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["operationId", "eid", "iccid"])

    eid_hash = _hash(payload["eid"])
    iccid_hash = _hash(payload["iccid"])
    reason = payload.get("reason")
    if reason and reason not in DISABLE_REASONS:
        reason = "userRequest"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("esimProfileOp", payload["operationId"])

    get_kotoba_client().insert_row("vertex_telecom_esim_profile_op", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "operation_id": payload['operationId'],
        "eid": eid_hash,
        "iccid": iccid_hash,
        "op_kind": 'disable',
        "reason": reason,
        "refresh_flag": False,
        "observed_at": observed_at,
        "status": 'disabled',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "iccid": iccid_hash, "status": "disabled"}


# ─── deleteEsimProfile ───────────────────────────────────────────────────────

def handle_delete_esim_profile(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["operationId", "eid", "iccid"])

    eid_hash = _hash(payload["eid"])
    iccid_hash = _hash(payload["iccid"])
    reason = payload.get("reason")
    if reason and reason not in DELETE_REASONS:
        reason = "userRequest"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("esimProfileOp", payload["operationId"])

    get_kotoba_client().insert_row("vertex_telecom_esim_profile_op", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "operation_id": payload['operationId'],
        "eid": eid_hash,
        "iccid": iccid_hash,
        "op_kind": 'delete',
        "reason": reason,
        "refresh_flag": False,
        "observed_at": observed_at,
        "status": 'deleted',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "iccid": iccid_hash, "status": "deleted"}


# ─── registerSmdpEvent ───────────────────────────────────────────────────────

def handle_register_smdp_event(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["eventId", "eid", "smdpAddress", "eventType"])

    eid_hash = _hash(payload["eid"])
    event_type = payload["eventType"]
    if event_type not in EVENT_TYPES:
        event_type = "profileDownload"

    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("smdsEvent", payload["eventId"])

    get_kotoba_client().insert_row("vertex_telecom_esim_smds_event", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "event_id": payload['eventId'],
        "eid": eid_hash,
        "smdp_address": payload['smdpAddress'],
        "smds_address": payload.get('smdsAddress'),
        "event_type": event_type,
        "iccid": _hash(payload.get('iccid')),
        "expires_at": payload.get('expiresAt'),
        "observed_at": observed_at,
        "status": 'pending',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "eventId": payload["eventId"], "status": "pending"}


# ─── auditEuiccState ─────────────────────────────────────────────────────────

def handle_audit_euicc_state(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["auditId", "eid"])

    eid_hash = _hash(payload["eid"])
    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("esimAudit", payload["auditId"])

    get_kotoba_client().insert_row("vertex_telecom_esim_audit", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "audit_id": payload['auditId'],
        "eid": eid_hash,
        "profile_count": payload.get('profileCount'),
        "active_iccid": _hash(payload.get('activeIccid')),
        "free_memory_bytes": payload.get('freeMemoryBytes'),
        "last_contact_at": payload.get('lastContactAt'),
        "observed_at": observed_at,
        "status": 'recorded',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "eid": eid_hash, "status": "recorded"}


# ─── transferEsimOwnership ───────────────────────────────────────────────────

def handle_transfer_esim_ownership(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, ["transferId", "eid", "iccid", "sourceMno", "targetMno", "targetSmdpAddress"])

    eid_hash = _hash(payload["eid"])
    iccid_hash = _hash(payload["iccid"])
    observed_at = payload.get("observedAt") or _now_iso()
    vertex_id = _vid("esimOwnershipTransfer", payload["transferId"])

    get_kotoba_client().insert_row("vertex_telecom_esim_ownership_transfer", {
        "vertex_id": vertex_id,
        "owner_did": TELECOM_DID,
        "transfer_id": payload['transferId'],
        "eid": eid_hash,
        "iccid": iccid_hash,
        "source_mno": payload['sourceMno'],
        "target_mno": payload['targetMno'],
        "target_smdp_address": payload['targetSmdpAddress'],
        "porting_ref": payload.get('portingRef'),
        "observed_at": observed_at,
        "status": 'initiated',
        "created_at": observed_at,
        "sensitivity_ord": 2,
        "org_id": payload.get('callerDid', TELECOM_DID),
        "user_id": payload.get('callerDid', TELECOM_DID),
        "actor_id": ACTOR_TAG,
    })

    return {"vertexId": vertex_id, "transferId": payload["transferId"], "status": "initiated"}


# ─── Worker registration ──────────────────────────────────────────────────────

def register(worker: Any, timeout_ms: int = 30_000) -> None:
    @worker.task(task_type="telecom.esim.euicc.provision", timeout_ms=timeout_ms)
    def _provision(payload: dict) -> dict:
        return handle_provision_euicc(payload)

    @worker.task(task_type="telecom.esim.profile.download", timeout_ms=timeout_ms)
    def _download(payload: dict) -> dict:
        return handle_download_esim_profile(payload)

    @worker.task(task_type="telecom.esim.profile.enable", timeout_ms=timeout_ms)
    def _enable(payload: dict) -> dict:
        return handle_enable_esim_profile(payload)

    @worker.task(task_type="telecom.esim.profile.disable", timeout_ms=timeout_ms)
    def _disable(payload: dict) -> dict:
        return handle_disable_esim_profile(payload)

    @worker.task(task_type="telecom.esim.profile.delete", timeout_ms=timeout_ms)
    def _delete(payload: dict) -> dict:
        return handle_delete_esim_profile(payload)

    @worker.task(task_type="telecom.esim.smds.register", timeout_ms=timeout_ms)
    def _smds(payload: dict) -> dict:
        return handle_register_smdp_event(payload)

    @worker.task(task_type="telecom.esim.euicc.audit", timeout_ms=timeout_ms)
    def _audit(payload: dict) -> dict:
        return handle_audit_euicc_state(payload)

    @worker.task(task_type="telecom.esim.profile.transfer", timeout_ms=timeout_ms)
    def _transfer(payload: dict) -> dict:
        return handle_transfer_esim_ownership(payload)
