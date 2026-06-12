"""telecom Phase 8 primitives — 5G Analytics + Service Routing + Roaming Security.

Eight BPMN service tasks bound to the telecom actor:

  - telecom.nwdaf.subscribe       (3GPP TS 23.288 Nnwdaf_AnalyticsSubscription)
  - telecom.nwdaf.result
  - telecom.scp.route             (3GPP TS 23.501 §6.2.18 SBI delegated routing)
  - telecom.scp.discover          (SCP-delegated NF discovery via NRF)
  - telecom.sepp.context          (3GPP TS 33.501 §13.2 N32 security context)
  - telecom.sepp.message          (N32-c / N32-f message audit)
  - telecom.sepp.keyRotate
  - telecom.sepp.trust

Cryptographic / payload handling:
  - TLS keys / PRINS keys / JWS signing keys / X.509 certs **never persist**;
    `certificateRef` and `newKeyRef` must be `vault://` pointers.
  - Key material persisted only as `sha256:` (or sha384/512) hashes for
    rotation audit trail.
  - SBI request URI (may contain SUPI/IMSI in query params) persisted only
    as sha256 hash. SBI / N32 message bodies never persisted; only
    `payloadHash` + `payloadSize` + security verification result.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.5g_security"

ANALYTICS_IDS = {
    "LOAD_LEVEL_INFORMATION", "NETWORK_PERFORMANCE", "SERVICE_EXPERIENCE",
    "UE_MOBILITY", "UE_COMMUNICATION", "ABNORMAL_BEHAVIOUR",
    "QOS_SUSTAINABILITY", "USER_DATA_CONGESTION", "DISPERSION",
    "WLAN_PERFORMANCE", "REDUNDANT_TRANSMISSION_EXP", "SM_CONGESTION",
    "NF_LOAD",
}
ANALYTICS_TARGET_KINDS = {"nfInstance", "ranNode", "cellSite", "subscriberProfile5g", "service", "snssai", "any"}
ACCURACY_LEVELS = {"low", "medium", "high"}
ROUTING_MODES = {"direct_a", "direct_b", "indirect_c", "indirect_d"}
METHOD_KINDS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
NF_TYPES = {"AMF", "SMF", "UPF", "UDM", "UDR", "AUSF", "PCF", "NRF", "NSSF", "NEF", "NWDAF", "CHF", "BSF"}
SELECTION_STRATEGIES = {"round_robin", "weighted", "priority", "least_load", "locality"}
N32_CIPHER_SUITES = {"TLS_AES_128_GCM_SHA256", "TLS_AES_256_GCM_SHA384",
                     "TLS_CHACHA20_POLY1305_SHA256", "PRINS"}
N32_CHANNELS = {"n32c", "n32f"}
SEPP_DIRECTIONS = {"inbound", "outbound"}
SECURITY_RESULTS = {"verified", "modification_detected", "decryption_failed", "signature_invalid", "timeout"}
KEY_KINDS = {"tls_session", "prins_modification", "prins_signature", "jws_signing"}
ROTATION_REASONS = {"scheduled", "compromise_suspected", "policy_change", "operator_request", "expired"}
NEGOTIATION_KINDS = {"initial", "rekey", "cipher_change", "policy_change", "ipx_introduction"}
MODIFICATION_POLICIES = {"none", "ipx_authorized", "ipx_restricted"}
NEGOTIATION_OUTCOMES = {"agreed", "rejected", "fallback", "timeout"}


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


def _require_vault_ref(value: str | None, field: str) -> None:
    if value and not value.startswith("vault://"):
        raise ValueError(f"{field} must be a vault:// pointer (raw value must not be persisted)")


def _require_hash_prefix(value: str, field: str) -> None:
    if not (value.startswith("sha256:") or value.startswith("sha384:") or value.startswith("sha512:")):
        raise ValueError(f"{field} must be prefixed with sha256:|sha384:|sha512:")


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_nwdaf_subscribe(
    consumerNfId: str = "", nwdafNfId: str = "", analyticsId: str = "",
    targetOfAnalyticsKind: str = "", targetOfAnalyticsVid: str = "",
    reportingPeriodSeconds: int = 0, observedAt: str = "",
    subscriptionId: str = "", snssai: str = "", dnn: str = "",
    accuracyRequirement: str = "", expiresAt: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"consumerNfId": consumerNfId, "nwdafNfId": nwdafNfId,
               "analyticsId": analyticsId,
               "targetOfAnalyticsKind": targetOfAnalyticsKind,
               "targetOfAnalyticsVid": targetOfAnalyticsVid,
               "reportingPeriodSeconds": reportingPeriodSeconds,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["consumerNfId", "nwdafNfId", "analyticsId",
                       "targetOfAnalyticsKind", "targetOfAnalyticsVid",
                       "reportingPeriodSeconds", "observedAt"])
    if analyticsId not in ANALYTICS_IDS:
        raise ValueError(f"unsupported analyticsId: {analyticsId}")
    if targetOfAnalyticsKind not in ANALYTICS_TARGET_KINDS:
        raise ValueError(f"unsupported targetOfAnalyticsKind: {targetOfAnalyticsKind}")
    if accuracyRequirement and accuracyRequirement not in ACCURACY_LEVELS:
        raise ValueError(f"unsupported accuracyRequirement: {accuracyRequirement}")
    period = int(reportingPeriodSeconds)
    if period <= 0:
        raise ValueError("reportingPeriodSeconds must be > 0")
    s_id = subscriptionId.strip() or _new_id("nwdsub", consumerNfId, analyticsId, targetOfAnalyticsVid)
    vid = _vid("nwdafSubscription", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "subscription_id": s_id,
        "consumer_nf_vid": _vid("nfInstance", consumerNfId),
        "nwdaf_nf_vid": _vid("nfInstance", nwdafNfId),
        "analytics_id": analyticsId,
        "target_of_analytics_kind": targetOfAnalyticsKind,
        "target_of_analytics_vid": targetOfAnalyticsVid,
        "snssai": snssai or None,
        "dnn": dnn or None,
        "reporting_period_seconds": period,
        "accuracy_requirement": accuracyRequirement or None,
        "expires_at": expiresAt or None,
        "observed_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_nwdaf_subscription", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "subscriptionId": s_id, "status": row["status"]}


def task_telecom_nwdaf_result(
    subscriptionId: str = "", analyticsId: str = "",
    sequenceNumber: int = 0, payloadHash: str = "", observedAt: str = "",
    resultId: str = "", confidence: float | None = None,
    validityPeriodSeconds: int | None = None,
    payloadRef: str = "", payloadSize: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"subscriptionId": subscriptionId, "analyticsId": analyticsId,
               "sequenceNumber": sequenceNumber, "payloadHash": payloadHash,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["subscriptionId", "analyticsId", "sequenceNumber",
                       "payloadHash", "observedAt"])
    seq = int(sequenceNumber)
    if seq <= 0:
        raise ValueError("sequenceNumber must be > 0")
    _require_hash_prefix(payloadHash, "payloadHash")
    _require_vault_ref(payloadRef, "payloadRef")
    r_id = resultId.strip() or _new_id("nwdres", subscriptionId, analyticsId, seq)
    vid = _vid("nwdafResult", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "result_id": r_id,
        "subscription_vid": _vid("nwdafSubscription", subscriptionId),
        "analytics_id": analyticsId,
        "sequence_number": seq,
        "confidence": float(confidence) if confidence is not None else None,
        "validity_period_seconds": int(validityPeriodSeconds) if validityPeriodSeconds is not None else None,
        "payload_hash": payloadHash,
        "payload_ref": payloadRef or None,
        "payload_size": int(payloadSize) if payloadSize is not None else None,
        "observed_at": observedAt,
        "status": "emitted",
        **_audit(payload),
    }
    _insert("vertex_telecom_nwdaf_result", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "resultId": r_id, "status": row["status"]}


def task_telecom_scp_route(
    scpNfId: str = "", sourceNfId: str = "", targetNfId: str = "",
    targetServiceName: str = "", routingMode: str = "",
    methodKind: str = "", statusCode: int = 0, observedAt: str = "",
    routeId: str = "", targetApiVersion: str = "",
    requestUriHash: str = "", latencyMs: float | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"scpNfId": scpNfId, "sourceNfId": sourceNfId,
               "targetNfId": targetNfId,
               "targetServiceName": targetServiceName,
               "routingMode": routingMode, "methodKind": methodKind,
               "statusCode": statusCode, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["scpNfId", "sourceNfId", "targetNfId",
                       "targetServiceName", "routingMode", "methodKind",
                       "statusCode", "observedAt"])
    if routingMode not in ROUTING_MODES:
        raise ValueError(f"unsupported routingMode: {routingMode}")
    if methodKind not in METHOD_KINDS:
        raise ValueError(f"unsupported methodKind: {methodKind}")
    code = int(statusCode)
    if code < 100 or code > 599:
        raise ValueError("statusCode must be a valid HTTP status (100-599)")
    if requestUriHash and not (requestUriHash.startswith("sha256:") or requestUriHash.startswith("sha384:") or requestUriHash.startswith("sha512:")):
        raise ValueError("requestUriHash must be sha256:|sha384:|sha512: prefixed")
    r_id = routeId.strip() or _new_id("scprt", sourceNfId, targetNfId, targetServiceName, observedAt)
    vid = _vid("scpRoute", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "route_id": r_id,
        "scp_nf_vid": _vid("nfInstance", scpNfId),
        "source_nf_vid": _vid("nfInstance", sourceNfId),
        "target_nf_vid": _vid("nfInstance", targetNfId),
        "target_service_name": targetServiceName,
        "target_api_version": targetApiVersion or None,
        "routing_mode": routingMode,
        "request_uri_hash": requestUriHash or None,
        "method_kind": methodKind,
        "status_code": code,
        "latency_ms": float(latencyMs) if latencyMs is not None else None,
        "observed_at": observedAt,
        "status": "routed" if 200 <= code < 400 else "failed",
        **_audit(payload),
    }
    _insert("vertex_telecom_scp_route", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "routeId": r_id, "status": row["status"]}


def task_telecom_scp_discover(
    scpNfId: str = "", requesterNfId: str = "", targetNfType: str = "",
    selectedNfId: str = "", observedAt: str = "",
    discoveryId: str = "", snssai: str = "", dnn: str = "", plmnId: str = "",
    candidateNfIds: Any = None, selectionStrategy: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"scpNfId": scpNfId, "requesterNfId": requesterNfId,
               "targetNfType": targetNfType, "selectedNfId": selectedNfId,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["scpNfId", "requesterNfId", "targetNfType",
                       "selectedNfId", "observedAt"])
    if targetNfType not in NF_TYPES:
        raise ValueError(f"unsupported targetNfType: {targetNfType}")
    if selectionStrategy and selectionStrategy not in SELECTION_STRATEGIES:
        raise ValueError(f"unsupported selectionStrategy: {selectionStrategy}")
    candidates = list(candidateNfIds) if isinstance(candidateNfIds, (list, tuple)) else []
    d_id = discoveryId.strip() or _new_id("scpdsc", requesterNfId, targetNfType, observedAt)
    vid = _vid("scpDiscovery", d_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "discovery_id": d_id,
        "scp_nf_vid": _vid("nfInstance", scpNfId),
        "requester_nf_vid": _vid("nfInstance", requesterNfId),
        "target_nf_type": targetNfType,
        "snssai": snssai or None,
        "dnn": dnn or None,
        "plmn_id": plmnId or None,
        "candidate_count": len(candidates),
        "candidate_nf_ids": _join(candidates),
        "selected_nf_vid": _vid("nfInstance", selectedNfId),
        "selection_strategy": selectionStrategy or None,
        "observed_at": observedAt,
        "status": "selected",
        **_audit(payload),
    }
    _insert("vertex_telecom_scp_discovery", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "discoveryId": d_id,
            "candidateCount": len(candidates), "status": row["status"]}


def task_telecom_sepp_context(
    localSeppNfId: str = "", remoteSeppFqdn: str = "",
    localPlmnId: str = "", remotePlmnId: str = "", agreementId: str = "",
    n32CipherSuite: str = "", validUntil: str = "", observedAt: str = "",
    contextId: str = "", telescopicFqdnEnabled: bool | None = None,
    certificateRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"localSeppNfId": localSeppNfId, "remoteSeppFqdn": remoteSeppFqdn,
               "localPlmnId": localPlmnId, "remotePlmnId": remotePlmnId,
               "agreementId": agreementId, "n32CipherSuite": n32CipherSuite,
               "validUntil": validUntil, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["localSeppNfId", "remoteSeppFqdn", "localPlmnId",
                       "remotePlmnId", "agreementId", "n32CipherSuite",
                       "validUntil", "observedAt"])
    if n32CipherSuite not in N32_CIPHER_SUITES:
        raise ValueError(f"unsupported n32CipherSuite: {n32CipherSuite}")
    _require_vault_ref(certificateRef, "certificateRef")
    c_id = contextId.strip() or _new_id("seppctx", localPlmnId, remotePlmnId, observedAt)
    vid = _vid("seppContext", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "context_id": c_id,
        "local_sepp_nf_vid": _vid("nfInstance", localSeppNfId),
        "remote_sepp_fqdn": remoteSeppFqdn,
        "local_plmn_id": localPlmnId,
        "remote_plmn_id": remotePlmnId,
        "agreement_vid": _vid("interconnectAgreement", agreementId),
        "n32_cipher_suite": n32CipherSuite,
        "telescopic_fqdn_enabled": bool(telescopicFqdnEnabled) if telescopicFqdnEnabled is not None else None,
        "certificate_ref": certificateRef or None,
        "established_at": observedAt,
        "valid_until": validUntil,
        "torn_down_at": None,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_sepp_context", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "contextId": c_id, "status": row["status"]}


def task_telecom_sepp_message(
    contextId: str = "", direction: str = "", n32Channel: str = "",
    payloadHash: str = "", securityResult: str = "", observedAt: str = "",
    messageId: str = "", modificationPolicyApplied: bool | None = None,
    payloadSize: int | None = None, latencyMs: float | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"contextId": contextId, "direction": direction,
               "n32Channel": n32Channel, "payloadHash": payloadHash,
               "securityResult": securityResult, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["contextId", "direction", "n32Channel",
                       "payloadHash", "securityResult", "observedAt"])
    if direction not in SEPP_DIRECTIONS:
        raise ValueError(f"unsupported direction: {direction}")
    if n32Channel not in N32_CHANNELS:
        raise ValueError(f"unsupported n32Channel: {n32Channel}")
    if securityResult not in SECURITY_RESULTS:
        raise ValueError(f"unsupported securityResult: {securityResult}")
    _require_hash_prefix(payloadHash, "payloadHash")
    m_id = messageId.strip() or _new_id("seppmsg", contextId, n32Channel, direction, observedAt)
    vid = _vid("seppMessage", m_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "message_id": m_id,
        "context_vid": _vid("seppContext", contextId),
        "direction": direction,
        "n32_channel": n32Channel,
        "modification_policy_applied": bool(modificationPolicyApplied) if modificationPolicyApplied is not None else None,
        "payload_hash": payloadHash,
        "payload_size": int(payloadSize) if payloadSize is not None else None,
        "security_result": securityResult,
        "latency_ms": float(latencyMs) if latencyMs is not None else None,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_sepp_message", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "messageId": m_id, "status": row["status"]}


def task_telecom_sepp_key_rotate(
    contextId: str = "", keyKind: str = "", newKeyHash: str = "",
    rotationReason: str = "", validUntil: str = "", observedAt: str = "",
    rotationId: str = "", oldKeyHash: str = "", newKeyRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"contextId": contextId, "keyKind": keyKind,
               "newKeyHash": newKeyHash, "rotationReason": rotationReason,
               "validUntil": validUntil, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["contextId", "keyKind", "newKeyHash",
                       "rotationReason", "validUntil", "observedAt"])
    if keyKind not in KEY_KINDS:
        raise ValueError(f"unsupported keyKind: {keyKind}")
    if rotationReason not in ROTATION_REASONS:
        raise ValueError(f"unsupported rotationReason: {rotationReason}")
    _require_hash_prefix(newKeyHash, "newKeyHash")
    if oldKeyHash:
        _require_hash_prefix(oldKeyHash, "oldKeyHash")
    _require_vault_ref(newKeyRef, "newKeyRef")
    r_id = rotationId.strip() or _new_id("seppkr", contextId, keyKind, observedAt)
    vid = _vid("seppKeyRotation", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "rotation_id": r_id,
        "context_vid": _vid("seppContext", contextId),
        "key_kind": keyKind,
        "old_key_hash": oldKeyHash or None,
        "new_key_hash": newKeyHash,
        "new_key_ref": newKeyRef or None,
        "rotation_reason": rotationReason,
        "valid_until": validUntil,
        "observed_at": observedAt,
        "status": "rotated",
        **_audit(payload),
    }
    _insert("vertex_telecom_sepp_key_rotation", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "rotationId": r_id, "status": row["status"]}


def task_telecom_sepp_trust(
    contextId: str = "", negotiationKind: str = "", outcome: str = "",
    observedAt: str = "",
    negotiationId: str = "", ipxProviderId: str = "",
    allowedCipherSuites: Any = None, agreedCipherSuite: str = "",
    modificationPolicy: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"contextId": contextId, "negotiationKind": negotiationKind,
               "outcome": outcome, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["contextId", "negotiationKind", "outcome", "observedAt"])
    if negotiationKind not in NEGOTIATION_KINDS:
        raise ValueError(f"unsupported negotiationKind: {negotiationKind}")
    if outcome not in NEGOTIATION_OUTCOMES:
        raise ValueError(f"unsupported outcome: {outcome}")
    if modificationPolicy and modificationPolicy not in MODIFICATION_POLICIES:
        raise ValueError(f"unsupported modificationPolicy: {modificationPolicy}")
    if agreedCipherSuite and agreedCipherSuite not in N32_CIPHER_SUITES:
        raise ValueError(f"unsupported agreedCipherSuite: {agreedCipherSuite}")
    n_id = negotiationId.strip() or _new_id("seppneg", contextId, negotiationKind, observedAt)
    vid = _vid("seppTrustNegotiation", n_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "negotiation_id": n_id,
        "context_vid": _vid("seppContext", contextId),
        "negotiation_kind": negotiationKind,
        "ipx_provider_id": ipxProviderId or None,
        "allowed_cipher_suites": _join(allowedCipherSuites),
        "agreed_cipher_suite": agreedCipherSuite or None,
        "modification_policy": modificationPolicy or None,
        "outcome": outcome,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_sepp_trust_negotiation", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "negotiationId": n_id,
            "outcome": outcome, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.nwdaf.subscribe", single_value=False, timeout_ms=timeout_ms)(task_telecom_nwdaf_subscribe)
    worker.task(task_type="telecom.nwdaf.result",    single_value=False, timeout_ms=timeout_ms)(task_telecom_nwdaf_result)
    worker.task(task_type="telecom.scp.route",       single_value=False, timeout_ms=timeout_ms)(task_telecom_scp_route)
    worker.task(task_type="telecom.scp.discover",    single_value=False, timeout_ms=timeout_ms)(task_telecom_scp_discover)
    worker.task(task_type="telecom.sepp.context",    single_value=False, timeout_ms=timeout_ms)(task_telecom_sepp_context)
    worker.task(task_type="telecom.sepp.message",    single_value=False, timeout_ms=timeout_ms)(task_telecom_sepp_message)
    worker.task(task_type="telecom.sepp.keyRotate",  single_value=False, timeout_ms=timeout_ms)(task_telecom_sepp_key_rotate)
    worker.task(task_type="telecom.sepp.trust",      single_value=False, timeout_ms=timeout_ms)(task_telecom_sepp_trust)
