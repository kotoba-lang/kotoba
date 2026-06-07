"""telecom Phase 11 primitives — Non-Public Networks (SNPN / PNI-NPN).

Eight BPMN service tasks (3GPP TS 23.501 §5.30 / TS 23.304 ProSe / TS 29.536 NSACF):

  - telecom.npn.snpn.register
  - telecom.npn.cag.register
  - telecom.npn.nid.register
  - telecom.npn.pni.provision
  - telecom.npn.idMap.upsert        (SUPI ↔ GPSI mapping in UDR)
  - telecom.npn.nsacf.enforce       (slice admission)
  - telecom.npn.prose.provision     (sidelink direct comm)
  - telecom.npn.subscriber.register

Discipline:
  - SUPI / GPSI persisted as sha256 hash. Raw IMSI/MSISDN never enter graph.
  - prosePolicyRef MUST be vault://. prosePolicyHash MUST be sha256:|sha384:|sha512:.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.npn"

DEPLOYMENT_KINDS = {"snpn_isolated", "snpn_with_phn", "snpn_with_credh", "shared_ran"}
ACCESS_KINDS = {"cag_only", "cag_preferred", "shared"}
NID_ASSIGNMENT_KINDS = {"self", "coordinated"}
ISOLATION_KINDS = {"dedicated_dnn", "dedicated_slice", "shared_dnn_with_qos"}
SLA_TIERS = {"bronze", "silver", "gold", "platinum"}
GPSI_KINDS = {"msisdn", "external_id", "imei", "external_uri"}
ID_ACTIONS = {"create", "update", "delete"}
NSACF_REQUEST_KINDS = {"registration", "pdu_session_establishment", "pdu_session_modification", "release"}
NSACF_DECISIONS = {"admit", "reject", "queue", "preempt"}
PROSE_COMM_KINDS = {"one_to_one", "one_to_many", "ue_to_network_relay", "ue_to_ue_relay"}
SIDELINK_PROFILES = {"pc5_mode_1", "pc5_mode_2", "ranged_mode"}
DEVICE_CLASSES = {"smartphone", "iot_sensor", "robot", "vehicle", "drone", "amr", "vr_headset", "mixed"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _hash_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _new_id(prefix: str, *parts: Any) -> str:
    if parts:
        digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]
        return f"{prefix}_{digest}"
    return f"{prefix}_{secrets.token_urlsafe(16).replace('-', '').replace('_', '')[:20]}"


def _join(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        items = [str(v).strip() for v in value if str(v).strip()]
        return ",".join(items) if items else None
    text = str(value).strip()
    return text or None


def _join_vids(values: Any, kind: str) -> str | None:
    if values is None or not isinstance(values, (list, tuple, set)):
        return None
    vids = [_vid(kind, str(v).strip()) for v in values if str(v).strip()]
    return ",".join(vids) if vids else None


def _require(payload: dict[str, Any], fields: list[str]) -> None:
    missing = [f for f in fields if payload.get(f) in (None, "")]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def _caller(payload: dict[str, Any]) -> str:
    return str(payload.get("callerDid") or TELECOM_DID)


def _audit(payload: dict[str, Any]) -> dict[str, Any]:
    did = _caller(payload)
    return {
        "created_at": _now_iso(),
        "sensitivity_ord": 2,
        "org_id": did,
        "user_id": did,
        "actor_id": ACTOR_TAG,
    }


def _insert(table: str, row: dict[str, Any], *, dry_run: bool = False) -> None:
    if dry_run:
        return
    get_kotoba_client().insert_row(table, row)


def _vid(kind: str, ident: str) -> str:
    return f"at://did:web:telecom.etzhayyim.com/com.etzhayyim.apps.telecom.{kind}/{ident}"


def _require_vault_ref(value: str | None, field: str) -> None:
    if value and not value.startswith("vault://"):
        raise ValueError(f"{field} must be a vault:// pointer")


def _require_hash_prefix(value: str, field: str) -> None:
    if not (value.startswith("sha256:") or value.startswith("sha384:") or value.startswith("sha512:")):
        raise ValueError(f"{field} must be prefixed with sha256:|sha384:|sha512:")


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_npn_snpn_register(
    enterpriseOrgId: str = "", deploymentKind: str = "", plmnId: str = "",
    nidValue: str = "", jurisdiction: str = "",
    validUntil: str = "", observedAt: str = "",
    snpnId: str = "", hostingNfIds: Any = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"enterpriseOrgId": enterpriseOrgId,
               "deploymentKind": deploymentKind, "plmnId": plmnId,
               "nidValue": nidValue, "jurisdiction": jurisdiction,
               "validUntil": validUntil, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["enterpriseOrgId", "deploymentKind", "plmnId",
                       "nidValue", "jurisdiction", "validUntil", "observedAt"])
    if deploymentKind not in DEPLOYMENT_KINDS:
        raise ValueError(f"unsupported deploymentKind: {deploymentKind}")
    s_id = snpnId.strip() or _new_id("snpn", enterpriseOrgId, plmnId, nidValue)
    vid = _vid("npnSnpnDeployment", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "snpn_id": s_id,
        "enterprise_org_id": enterpriseOrgId,
        "deployment_kind": deploymentKind,
        "plmn_id": plmnId, "nid_value": nidValue,
        "hosting_nf_vids": _join_vids(hostingNfIds, "nfInstance"),
        "jurisdiction": jurisdiction,
        "registered_at": observedAt,
        "valid_until": validUntil,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_npn_snpn_deployment", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "snpnId": s_id, "status": row["status"]}


def task_telecom_npn_cag_register(
    snpnId: str = "", cagValue: str = "", displayName: str = "",
    accessKind: str = "", observedAt: str = "",
    cagId: str = "", allowedCellSiteIds: Any = None,
    allowedRanNodeIds: Any = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"snpnId": snpnId, "cagValue": cagValue,
               "displayName": displayName, "accessKind": accessKind,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["snpnId", "cagValue", "displayName", "accessKind", "observedAt"])
    if accessKind not in ACCESS_KINDS:
        raise ValueError(f"unsupported accessKind: {accessKind}")
    c_id = cagId.strip() or _new_id("cag", snpnId, cagValue)
    vid = _vid("npnCag", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "cag_id": c_id,
        "snpn_vid": _vid("npnSnpnDeployment", snpnId),
        "cag_value": cagValue,
        "display_name": displayName,
        "allowed_cell_site_vids": _join_vids(allowedCellSiteIds, "cellSite"),
        "allowed_ran_node_vids": _join_vids(allowedRanNodeIds, "ranNode"),
        "access_kind": accessKind,
        "observed_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_npn_cag", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "cagId": c_id, "status": row["status"]}


def task_telecom_npn_nid_register(
    snpnId: str = "", nidValue: str = "", assignmentKind: str = "",
    allocatedAt: str = "", observedAt: str = "",
    allocationId: str = "", ouiPrefix: str = "", ieeeAuthorityRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"snpnId": snpnId, "nidValue": nidValue,
               "assignmentKind": assignmentKind,
               "allocatedAt": allocatedAt, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["snpnId", "nidValue", "assignmentKind",
                       "allocatedAt", "observedAt"])
    if assignmentKind not in NID_ASSIGNMENT_KINDS:
        raise ValueError(f"unsupported assignmentKind: {assignmentKind}")
    if assignmentKind == "coordinated" and not ouiPrefix:
        raise ValueError("ouiPrefix is required for coordinated assignment")
    a_id = allocationId.strip() or _new_id("nid", snpnId, nidValue, assignmentKind)
    vid = _vid("npnNidAllocation", a_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "allocation_id": a_id,
        "snpn_vid": _vid("npnSnpnDeployment", snpnId),
        "nid_value": nidValue,
        "assignment_kind": assignmentKind,
        "oui_prefix": ouiPrefix or None,
        "ieee_authority_ref": ieeeAuthorityRef or None,
        "allocated_at": allocatedAt,
        "observed_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_npn_nid_allocation", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "allocationId": a_id, "status": row["status"]}


def task_telecom_npn_pni_provision(
    enterpriseOrgId: str = "", hostingPlmnId: str = "", snssai: str = "",
    dnn: str = "", isolationKind: str = "", slaTier: str = "",
    validUntil: str = "", observedAt: str = "",
    pniId: str = "", cagId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"enterpriseOrgId": enterpriseOrgId,
               "hostingPlmnId": hostingPlmnId, "snssai": snssai, "dnn": dnn,
               "isolationKind": isolationKind, "slaTier": slaTier,
               "validUntil": validUntil, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["enterpriseOrgId", "hostingPlmnId", "snssai",
                       "dnn", "isolationKind", "slaTier",
                       "validUntil", "observedAt"])
    if isolationKind not in ISOLATION_KINDS:
        raise ValueError(f"unsupported isolationKind: {isolationKind}")
    if slaTier not in SLA_TIERS:
        raise ValueError(f"unsupported slaTier: {slaTier}")
    p_id = pniId.strip() or _new_id("pni", enterpriseOrgId, hostingPlmnId, snssai, dnn)
    vid = _vid("npnPniSlice", p_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "pni_id": p_id,
        "enterprise_org_id": enterpriseOrgId,
        "hosting_plmn_id": hostingPlmnId,
        "snssai": snssai, "dnn": dnn,
        "cag_vid": _vid("npnCag", cagId) if cagId else None,
        "isolation_kind": isolationKind,
        "sla_tier": slaTier,
        "provisioned_at": observedAt,
        "valid_until": validUntil,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_npn_pni_slice", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "pniId": p_id, "status": row["status"]}


def task_telecom_npn_id_map_upsert(
    profileId: str = "", supi: str = "", gpsiKind: str = "",
    gpsiValue: str = "", action: str = "", observedAt: str = "",
    mappingId: str = "", snpnId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"profileId": profileId, "supi": supi,
               "gpsiKind": gpsiKind, "gpsiValue": gpsiValue,
               "action": action, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["profileId", "supi", "gpsiKind", "gpsiValue",
                       "action", "observedAt"])
    if gpsiKind not in GPSI_KINDS:
        raise ValueError(f"unsupported gpsiKind: {gpsiKind}")
    if action not in ID_ACTIONS:
        raise ValueError(f"unsupported action: {action}")
    m_id = mappingId.strip() or _new_id("idmap", profileId, gpsiKind, gpsiValue)
    vid = _vid("npnIdMapping", m_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "mapping_id": m_id,
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "supi_hash": _hash_id(supi),
        "gpsi_kind": gpsiKind,
        "gpsi_hash": _hash_id(gpsiValue),
        "snpn_vid": _vid("npnSnpnDeployment", snpnId) if snpnId else None,
        "action": action,
        "observed_at": observedAt,
        "status": "active" if action != "delete" else "deleted",
        **_audit(payload),
    }
    _insert("vertex_telecom_npn_id_mapping", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "mappingId": m_id, "status": row["status"]}


def task_telecom_npn_nsacf_enforce(
    nsacfNfId: str = "", snssai: str = "", requesterNfId: str = "",
    requestKind: str = "", decision: str = "", observedAt: str = "",
    decisionId: str = "", snpnId: str = "", profileId: str = "",
    currentRegisteredUes: int | None = None,
    currentEstablishedSessions: int | None = None,
    maxRegisteredUes: int | None = None,
    maxEstablishedSessions: int | None = None,
    decisionReason: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"nsacfNfId": nsacfNfId, "snssai": snssai,
               "requesterNfId": requesterNfId, "requestKind": requestKind,
               "decision": decision, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["nsacfNfId", "snssai", "requesterNfId",
                       "requestKind", "decision", "observedAt"])
    if requestKind not in NSACF_REQUEST_KINDS:
        raise ValueError(f"unsupported requestKind: {requestKind}")
    if decision not in NSACF_DECISIONS:
        raise ValueError(f"unsupported decision: {decision}")
    d_id = decisionId.strip() or _new_id("nsacf", snssai, requesterNfId, observedAt)
    vid = _vid("npnNsacfDecision", d_id)
    admit = decision == "admit"
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "decision_id": d_id,
        "nsacf_nf_vid": _vid("nfInstance", nsacfNfId),
        "snssai": snssai,
        "snpn_vid": _vid("npnSnpnDeployment", snpnId) if snpnId else None,
        "requester_nf_vid": _vid("nfInstance", requesterNfId),
        "profile_vid": _vid("subscriberProfile5g", profileId) if profileId else None,
        "request_kind": requestKind,
        "current_registered_ues": int(currentRegisteredUes) if currentRegisteredUes is not None else None,
        "current_established_sessions": int(currentEstablishedSessions) if currentEstablishedSessions is not None else None,
        "max_registered_ues": int(maxRegisteredUes) if maxRegisteredUes is not None else None,
        "max_established_sessions": int(maxEstablishedSessions) if maxEstablishedSessions is not None else None,
        "decision": decision,
        "decision_reason": decisionReason or None,
        "admit": admit,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_npn_nsacf_decision", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "decisionId": d_id, "admit": admit, "status": row["status"]}


def task_telecom_npn_prose_provision(
    snpnId: str = "", communicationKind: str = "",
    prosePolicyHash: str = "", validUntil: str = "", observedAt: str = "",
    proseId: str = "", layer2GroupId: str = "",
    prosePolicyRef: str = "", sidelinkProfile: str = "",
    allowedRanNodeIds: Any = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"snpnId": snpnId, "communicationKind": communicationKind,
               "prosePolicyHash": prosePolicyHash,
               "validUntil": validUntil, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["snpnId", "communicationKind", "prosePolicyHash",
                       "validUntil", "observedAt"])
    if communicationKind not in PROSE_COMM_KINDS:
        raise ValueError(f"unsupported communicationKind: {communicationKind}")
    if sidelinkProfile and sidelinkProfile not in SIDELINK_PROFILES:
        raise ValueError(f"unsupported sidelinkProfile: {sidelinkProfile}")
    _require_hash_prefix(prosePolicyHash, "prosePolicyHash")
    _require_vault_ref(prosePolicyRef, "prosePolicyRef")
    p_id = proseId.strip() or _new_id("prose", snpnId, communicationKind, observedAt)
    vid = _vid("npnProsePolicy", p_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "prose_id": p_id,
        "snpn_vid": _vid("npnSnpnDeployment", snpnId),
        "communication_kind": communicationKind,
        "layer2_group_id": layer2GroupId or None,
        "prose_policy_hash": prosePolicyHash,
        "prose_policy_ref": prosePolicyRef or None,
        "sidelink_profile": sidelinkProfile or None,
        "allowed_ran_node_vids": _join_vids(allowedRanNodeIds, "ranNode"),
        "provisioned_at": observedAt,
        "valid_until": validUntil,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_npn_prose_policy", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "proseId": p_id, "status": row["status"]}


def task_telecom_npn_subscriber_register(
    profileId: str = "", sponsoredByEnterpriseOrgId: str = "",
    validUntil: str = "", observedAt: str = "",
    enrollmentId: str = "", snpnId: str = "", pniId: str = "",
    cagIds: Any = None, allowedDeviceClass: str = "",
    deviceCount: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"profileId": profileId,
               "sponsoredByEnterpriseOrgId": sponsoredByEnterpriseOrgId,
               "validUntil": validUntil, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["profileId", "sponsoredByEnterpriseOrgId",
                       "validUntil", "observedAt"])
    if not (snpnId or pniId):
        raise ValueError("either snpnId or pniId must be provided")
    if allowedDeviceClass and allowedDeviceClass not in DEVICE_CLASSES:
        raise ValueError(f"unsupported allowedDeviceClass: {allowedDeviceClass}")
    e_id = enrollmentId.strip() or _new_id("npnenr", profileId, snpnId or pniId, observedAt)
    vid = _vid("npnSubscriberEnrollment", e_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "enrollment_id": e_id,
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "snpn_vid": _vid("npnSnpnDeployment", snpnId) if snpnId else None,
        "pni_vid": _vid("npnPniSlice", pniId) if pniId else None,
        "cag_vids": _join_vids(cagIds, "npnCag"),
        "allowed_device_class": allowedDeviceClass or None,
        "device_count": int(deviceCount) if deviceCount is not None else None,
        "sponsored_by_enterprise_org_id": sponsoredByEnterpriseOrgId,
        "enrolled_at": observedAt,
        "valid_until": validUntil,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_npn_subscriber_enrollment", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "enrollmentId": e_id, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.npn.snpn.register",       single_value=False, timeout_ms=timeout_ms)(task_telecom_npn_snpn_register)
    worker.task(task_type="telecom.npn.cag.register",        single_value=False, timeout_ms=timeout_ms)(task_telecom_npn_cag_register)
    worker.task(task_type="telecom.npn.nid.register",        single_value=False, timeout_ms=timeout_ms)(task_telecom_npn_nid_register)
    worker.task(task_type="telecom.npn.pni.provision",       single_value=False, timeout_ms=timeout_ms)(task_telecom_npn_pni_provision)
    worker.task(task_type="telecom.npn.idMap.upsert",        single_value=False, timeout_ms=timeout_ms)(task_telecom_npn_id_map_upsert)
    worker.task(task_type="telecom.npn.nsacf.enforce",       single_value=False, timeout_ms=timeout_ms)(task_telecom_npn_nsacf_enforce)
    worker.task(task_type="telecom.npn.prose.provision",     single_value=False, timeout_ms=timeout_ms)(task_telecom_npn_prose_provision)
    worker.task(task_type="telecom.npn.subscriber.register", single_value=False, timeout_ms=timeout_ms)(task_telecom_npn_subscriber_register)
