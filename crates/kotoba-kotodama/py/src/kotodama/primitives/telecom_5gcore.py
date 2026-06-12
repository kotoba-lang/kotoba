"""telecom Phase 4 primitives — 5G Core SBA control plane.

Eight BPMN service tasks bound to the telecom actor:

  - telecom.nf.register
  - telecom.subscriberProfile5g.register
  - telecom.subscriber.authenticate
  - telecom.amf.register
  - telecom.slice.select
  - telecom.policy.apply
  - telecom.session.establish
  - telecom.charging.emit

Crypto handling: SUPI is persisted only as a `sha256:` hash. AKA K /
RES* / KAUSF must never be persisted — `akaCredentialRef` is a
`vault://` pointer (Phase 1 vault), not a literal value. The
`task_telecom_subscriber_authenticate` handler stores only event
metadata (method / outcome / serving network / a non-reversible
randHash for correlation), never the challenge or response material.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.5gcore"

NF_TYPES = {"AMF", "SMF", "UPF", "UDM", "UDR", "AUSF", "PCF", "NRF", "NSSF", "NEF", "NWDAF", "CHF", "BSF"}
AUTH_METHODS = {"5G-AKA", "EAP-AKA-prime", "EAP-TLS"}
AUTH_RESULTS = {"success", "failure", "synchronization-failure"}
REG_TYPES = {"initial", "mobility", "periodic", "emergency"}
SESSION_TYPES = {"IPv4", "IPv6", "IPv4v6", "Ethernet", "Unstructured"}
CHARGING_METHODS = {"online", "offline", "converged"}
USAGE_UNITS = {"seconds", "messages", "bytes", "events"}


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


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_nf_register(
    nfType: str = "", plmnId: str = "",
    nfInstanceId: str = "", sNssaiList: Any = None, fqdn: str = "",
    ipv4Address: str = "", capacity: int | None = None,
    priority: int | None = None, heartbeatInterval: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"nfType": nfType, "plmnId": plmnId, "callerDid": callerDid}
    _require(payload, ["nfType", "plmnId"])
    if nfType not in NF_TYPES:
        raise ValueError(f"unsupported nfType: {nfType}")
    n_id = nfInstanceId.strip() or _new_id("nf", nfType, plmnId, fqdn or ipv4Address or "")
    vid = _vid("nfInstance", n_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "nf_instance_id": n_id, "nf_type": nfType, "plmn_id": plmnId,
        "s_nssai_list": _join(sNssaiList),
        "fqdn": fqdn or None,
        "ipv4_address": ipv4Address or None,
        "capacity": int(capacity) if capacity is not None else None,
        "priority": int(priority) if priority is not None else None,
        "heartbeat_interval": int(heartbeatInterval) if heartbeatInterval is not None else None,
        "registered_at": _now_iso(),
        "status": "registered", **_audit(payload),
    }
    _insert("vertex_telecom_nf_instance", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "nfInstanceId": n_id, "status": row["status"]}


def task_telecom_subscriber_profile_5g_register(
    subscriberId: str = "", supi: str = "", dnnList: Any = None,
    profileId: str = "", suciSchemeId: str = "",
    sliceSubscriptionList: Any = None,
    ambrUplinkKbps: int | None = None, ambrDownlinkKbps: int | None = None,
    akaCredentialRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"subscriberId": subscriberId, "supi": supi, "dnnList": dnnList, "callerDid": callerDid}
    _require(payload, ["subscriberId", "supi", "dnnList"])
    if akaCredentialRef and not akaCredentialRef.startswith("vault://"):
        raise ValueError("akaCredentialRef must be a vault:// pointer (raw K must not be persisted)")
    p_id = profileId.strip() or _new_id("p5g", subscriberId, supi)
    vid = _vid("subscriberProfile5g", p_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "profile_id": p_id,
        "subscriber_vid": _vid("subscriber", subscriberId),
        "supi_hash": _hash_id(supi),
        "suci_scheme_id": suciSchemeId or None,
        "slice_subscription_list": _join(sliceSubscriptionList),
        "dnn_list": _join(dnnList),
        "ambr_uplink_kbps": int(ambrUplinkKbps) if ambrUplinkKbps is not None else None,
        "ambr_downlink_kbps": int(ambrDownlinkKbps) if ambrDownlinkKbps is not None else None,
        "aka_credential_ref": akaCredentialRef or None,
        "status": "active",
        "provisioned_at": _now_iso(),
        **_audit(payload),
    }
    _insert("vertex_telecom_subscriber_profile_5g", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "profileId": p_id, "status": row["status"]}


def task_telecom_subscriber_authenticate(
    profileId: str = "", supi: str = "", authMethod: str = "",
    result: str = "", observedAt: str = "",
    authEventId: str = "", servingNetwork: str = "",
    randHash: str = "", ausfNfId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"profileId": profileId, "supi": supi, "authMethod": authMethod,
               "result": result, "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["profileId", "supi", "authMethod", "result", "observedAt"])
    if authMethod not in AUTH_METHODS:
        raise ValueError(f"unsupported authMethod: {authMethod}")
    if result not in AUTH_RESULTS:
        raise ValueError(f"unsupported result: {result}")
    if randHash and len(randHash) > 0 and not randHash.startswith("sha256:"):
        randHash = _hash_id(randHash)
    e_id = authEventId.strip() or _new_id("auth", profileId, observedAt, result)
    vid = _vid("authEvent", e_id)
    success = result == "success"
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "auth_event_id": e_id,
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "supi_hash": _hash_id(supi),
        "serving_network": servingNetwork or None,
        "auth_method": authMethod, "result": result, "success": success,
        "rand_hash": randHash or None,
        "ausf_nf_vid": _vid("nfInstance", ausfNfId) if ausfNfId else None,
        "observed_at": observedAt,
        "status": "recorded", **_audit(payload),
    }
    _insert("vertex_telecom_auth_event", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "authEventId": e_id, "success": success, "status": row["status"]}


def task_telecom_amf_register(
    profileId: str = "", registrationType: str = "",
    ranNodeId: str = "", amfNfId: str = "", observedAt: str = "",
    registrationId: str = "", supi: str = "",
    taiPlmnId: str = "", taiTac: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"profileId": profileId, "registrationType": registrationType,
               "ranNodeId": ranNodeId, "amfNfId": amfNfId,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["profileId", "registrationType", "ranNodeId", "amfNfId", "observedAt"])
    if registrationType not in REG_TYPES:
        raise ValueError(f"unsupported registrationType: {registrationType}")
    r_id = registrationId.strip() or _new_id("amfreg", profileId, ranNodeId, observedAt, registrationType)
    vid = _vid("amfRegistration", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "registration_id": r_id,
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "supi_hash": _hash_id(supi) if supi else None,
        "registration_type": registrationType,
        "ran_node_vid": _vid("ranNode", ranNodeId),
        "amf_nf_vid": _vid("nfInstance", amfNfId),
        "tai_plmn_id": taiPlmnId or None,
        "tai_tac": taiTac or None,
        "observed_at": observedAt,
        "status": "registered", **_audit(payload),
    }
    _insert("vertex_telecom_amf_registration", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "registrationId": r_id, "status": row["status"]}


def task_telecom_slice_select(
    registrationId: str = "", profileId: str = "",
    selectedSnssai: str = "", nssfNfId: str = "", observedAt: str = "",
    selectionId: str = "", requestedNssaiList: Any = None,
    allowedNssaiList: Any = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"registrationId": registrationId, "profileId": profileId,
               "selectedSnssai": selectedSnssai, "nssfNfId": nssfNfId,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["registrationId", "profileId", "selectedSnssai", "nssfNfId", "observedAt"])
    s_id = selectionId.strip() or _new_id("nssf", registrationId, selectedSnssai, observedAt)
    vid = _vid("sliceSelection", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "selection_id": s_id,
        "registration_vid": _vid("amfRegistration", registrationId),
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "requested_nssai_list": _join(requestedNssaiList),
        "allowed_nssai_list": _join(allowedNssaiList),
        "selected_snssai": selectedSnssai,
        "nssf_nf_vid": _vid("nfInstance", nssfNfId),
        "observed_at": observedAt,
        "status": "selected", **_audit(payload),
    }
    _insert("vertex_telecom_slice_selection", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "selectionId": s_id, "status": row["status"]}


def task_telecom_policy_apply(
    profileId: str = "", snssai: str = "", dnn: str = "",
    chargingMethod: str = "", pcfNfId: str = "", observedAt: str = "",
    decisionId: str = "", sessionId: str = "",
    qosFlowList: Any = None, ratingGroup: str = "", sponsorId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"profileId": profileId, "snssai": snssai, "dnn": dnn,
               "chargingMethod": chargingMethod, "pcfNfId": pcfNfId,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["profileId", "snssai", "dnn", "chargingMethod", "pcfNfId", "observedAt"])
    if chargingMethod not in CHARGING_METHODS:
        raise ValueError(f"unsupported chargingMethod: {chargingMethod}")
    d_id = decisionId.strip() or _new_id("pcf", profileId, snssai, dnn, observedAt)
    vid = _vid("policyDecision", d_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "decision_id": d_id,
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "session_vid": _vid("pduSession", sessionId) if sessionId else None,
        "snssai": snssai, "dnn": dnn,
        "qos_flow_list": _join(qosFlowList),
        "charging_method": chargingMethod,
        "rating_group": ratingGroup or None,
        "sponsor_id": sponsorId or None,
        "pcf_nf_vid": _vid("nfInstance", pcfNfId),
        "observed_at": observedAt,
        "status": "applied", **_audit(payload),
    }
    _insert("vertex_telecom_policy_decision", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "decisionId": d_id, "status": row["status"]}


def task_telecom_session_establish(
    registrationId: str = "", profileId: str = "",
    snssai: str = "", dnn: str = "", sessionType: str = "",
    smfNfId: str = "", observedAt: str = "",
    sessionId: str = "", upfNfId: str = "", ranNodeId: str = "",
    policyDecisionId: str = "", ueIpv4: str = "", ueIpv6Prefix: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"registrationId": registrationId, "profileId": profileId,
               "snssai": snssai, "dnn": dnn, "sessionType": sessionType,
               "smfNfId": smfNfId, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["registrationId", "profileId", "snssai", "dnn", "sessionType", "smfNfId", "observedAt"])
    if sessionType not in SESSION_TYPES:
        raise ValueError(f"unsupported sessionType: {sessionType}")
    s_id = sessionId.strip() or _new_id("pdu", registrationId, snssai, dnn, observedAt)
    vid = _vid("pduSession", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "session_id": s_id,
        "registration_vid": _vid("amfRegistration", registrationId),
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "snssai": snssai, "dnn": dnn, "session_type": sessionType,
        "smf_nf_vid": _vid("nfInstance", smfNfId),
        "upf_nf_vid": _vid("nfInstance", upfNfId) if upfNfId else None,
        "ran_node_vid": _vid("ranNode", ranNodeId) if ranNodeId else None,
        "policy_decision_vid": _vid("policyDecision", policyDecisionId) if policyDecisionId else None,
        "ue_ipv4": ueIpv4 or None,
        "ue_ipv6_prefix": ueIpv6Prefix or None,
        "established_at": observedAt,
        "released_at": None,
        "status": "active", **_audit(payload),
    }
    _insert("vertex_telecom_pdu_session", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "sessionId": s_id, "status": row["status"]}


def task_telecom_charging_emit(
    sessionId: str = "", profileId: str = "", subscriberId: str = "",
    ratingGroup: str = "", units: float = 0.0,
    currency: str = "", amount: float = 0.0,
    chargingMethod: str = "", startedAt: str = "",
    chargingId: str = "", unitOfMeasure: str = "",
    chfNfId: str = "", endedAt: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"sessionId": sessionId, "profileId": profileId,
               "subscriberId": subscriberId, "ratingGroup": ratingGroup,
               "currency": currency, "chargingMethod": chargingMethod,
               "startedAt": startedAt, "callerDid": callerDid}
    _require(payload, ["sessionId", "profileId", "subscriberId", "ratingGroup",
                       "currency", "chargingMethod", "startedAt"])
    if chargingMethod not in CHARGING_METHODS:
        raise ValueError(f"unsupported chargingMethod: {chargingMethod}")
    if unitOfMeasure and unitOfMeasure not in USAGE_UNITS:
        raise ValueError(f"unsupported unitOfMeasure: {unitOfMeasure}")
    units_f = float(units)
    amount_f = float(amount)
    if units_f < 0 or amount_f < 0:
        raise ValueError("units and amount must be non-negative")
    c_id = chargingId.strip() or _new_id("chg", sessionId, ratingGroup, startedAt)
    vid = _vid("chargingRecord", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "charging_id": c_id,
        "session_vid": _vid("pduSession", sessionId),
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "subscriber_vid": _vid("subscriber", subscriberId),
        "rating_group": ratingGroup,
        "units": units_f, "unit_of_measure": unitOfMeasure or None,
        "currency": currency, "amount": amount_f,
        "charging_method": chargingMethod,
        "chf_nf_vid": _vid("nfInstance", chfNfId) if chfNfId else None,
        "started_at": startedAt, "ended_at": endedAt or None,
        "status": "emitted", **_audit(payload),
    }
    _insert("vertex_telecom_charging_record", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "chargingId": c_id, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.nf.register",                  single_value=False, timeout_ms=timeout_ms)(task_telecom_nf_register)
    worker.task(task_type="telecom.subscriberProfile5g.register", single_value=False, timeout_ms=timeout_ms)(task_telecom_subscriber_profile_5g_register)
    worker.task(task_type="telecom.subscriber.authenticate",      single_value=False, timeout_ms=timeout_ms)(task_telecom_subscriber_authenticate)
    worker.task(task_type="telecom.amf.register",                 single_value=False, timeout_ms=timeout_ms)(task_telecom_amf_register)
    worker.task(task_type="telecom.slice.select",                 single_value=False, timeout_ms=timeout_ms)(task_telecom_slice_select)
    worker.task(task_type="telecom.policy.apply",                 single_value=False, timeout_ms=timeout_ms)(task_telecom_policy_apply)
    worker.task(task_type="telecom.session.establish",            single_value=False, timeout_ms=timeout_ms)(task_telecom_session_establish)
    worker.task(task_type="telecom.charging.emit",                single_value=False, timeout_ms=timeout_ms)(task_telecom_charging_emit)
