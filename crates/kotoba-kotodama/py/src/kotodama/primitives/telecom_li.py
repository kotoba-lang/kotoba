"""telecom Phase 6 primitives — Lawful Intercept (CALEA / ETSI LI / 3GPP TS 33.127).

Eight BPMN service tasks bound to the telecom actor:

  - telecom.li.warrant.register
  - telecom.li.target.activate
  - telecom.li.target.deactivate
  - telecom.li.iri.deliver         (DF2 / X2 — Intercept-Related Information)
  - telecom.li.cc.deliver          (DF3 / X3 — Communication Content)
  - telecom.li.delivery.ack        (LEMF acknowledgement, computes loss)
  - telecom.li.audit.access        (operator-side LI access audit)
  - telecom.li.warrant.close

PII / payload handling — strictest in the entire telecom actor:

  - identifierValue (MSISDN / IMSI / SUPI / IMPU / IMPI / IPv4 / IPv6 /
    email / IMEI), warrantNumber, accessor identity all persisted as
    `sha256:` hashes.
  - warrantDocumentRef / encryptionRef must be `vault://` pointers; raw
    warrant bodies and encryption keys never persist in graph.
  - payloadHash is the sha256 of the IRI / CC payload; the payload
    itself goes DF2/DF3 → LEMF directly. Graph holds only metadata.
  - sensitivity_ord = 4 for every Phase 6 row (above PII Tier 3).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.li"
LI_SENSITIVITY = 4

WARRANT_KINDS = {"court_order", "national_security", "emergency", "administrative"}
INTERCEPT_SCOPES = {"iri_only", "cc_only", "iri_and_cc"}
IDENTIFIER_KINDS = {"msisdn", "imsi", "supi", "impu", "impi", "ipv4", "ipv6", "email", "imei"}
DEACT_REASONS = {"warrant_expired", "warrant_revoked", "target_resolved", "court_order", "operator_request"}
IRI_EVENT_KINDS = {"registration", "session_establish", "session_release", "voice_setup",
                   "voice_release", "sms", "supp_service", "location_update", "handover"}
CC_KINDS = {"voice_rtp", "data_pdu", "sms_payload", "ims_media", "video_rtp"}
DELIVERY_KINDS = {"iri", "cc"}
ACK_RESULTS = {"received", "checksum_failure", "decode_failure", "timeout", "rejected"}
ACCESS_KINDS = {"read", "query", "export", "modify", "delete"}
ACCESSOR_ROLES = {"li_admin", "li_operator", "compliance_officer", "regulator", "system"}
RECORD_KINDS = {"warrant", "target", "iri", "cc", "ack"}
CLOSURE_REASONS = {"expired", "revoked", "investigation_complete", "operator_request", "court_order"}


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
        "sensitivity_ord": LI_SENSITIVITY,
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


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_li_warrant_register(
    jurisdiction: str = "", lawAuthorityId: str = "", warrantNumber: str = "",
    warrantKind: str = "", interceptScope: str = "",
    validFrom: str = "", validUntil: str = "", lemfId: str = "",
    warrantId: str = "", warrantDocumentRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"jurisdiction": jurisdiction, "lawAuthorityId": lawAuthorityId,
               "warrantNumber": warrantNumber, "warrantKind": warrantKind,
               "interceptScope": interceptScope, "validFrom": validFrom,
               "validUntil": validUntil, "lemfId": lemfId, "callerDid": callerDid}
    _require(payload, ["jurisdiction", "lawAuthorityId", "warrantNumber",
                       "warrantKind", "interceptScope", "validFrom",
                       "validUntil", "lemfId"])
    if warrantKind not in WARRANT_KINDS:
        raise ValueError(f"unsupported warrantKind: {warrantKind}")
    if interceptScope not in INTERCEPT_SCOPES:
        raise ValueError(f"unsupported interceptScope: {interceptScope}")
    _require_vault_ref(warrantDocumentRef, "warrantDocumentRef")
    w_id = warrantId.strip() or _new_id("warr", jurisdiction, lawAuthorityId, warrantNumber)
    vid = _vid("liWarrant", w_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "warrant_id": w_id,
        "jurisdiction": jurisdiction,
        "law_authority_id": lawAuthorityId,
        "warrant_number_hash": _hash_id(warrantNumber),
        "warrant_kind": warrantKind,
        "intercept_scope": interceptScope,
        "valid_from": validFrom, "valid_until": validUntil,
        "lemf_id": lemfId,
        "warrant_document_ref": warrantDocumentRef or None,
        "registered_at": _now_iso(),
        "closed_at": None, "closure_reason": None,
        "retention_until": None, "final_report_ref": None,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_li_warrant", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "warrantId": w_id, "status": row["status"]}


def task_telecom_li_target_activate(
    warrantId: str = "", identifierKind: str = "", identifierValue: str = "",
    licfNfId: str = "", x1ProvisionedAt: str = "",
    targetId: str = "", lipfNfId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"warrantId": warrantId, "identifierKind": identifierKind,
               "identifierValue": identifierValue, "licfNfId": licfNfId,
               "x1ProvisionedAt": x1ProvisionedAt, "callerDid": callerDid}
    _require(payload, ["warrantId", "identifierKind", "identifierValue",
                       "licfNfId", "x1ProvisionedAt"])
    if identifierKind not in IDENTIFIER_KINDS:
        raise ValueError(f"unsupported identifierKind: {identifierKind}")
    t_id = targetId.strip() or _new_id("tgt", warrantId, identifierKind, identifierValue)
    vid = _vid("liTarget", t_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "target_id": t_id,
        "warrant_vid": _vid("liWarrant", warrantId),
        "identifier_kind": identifierKind,
        "identifier_hash": _hash_id(identifierValue),
        "licf_nf_vid": _vid("nfInstance", licfNfId),
        "lipf_nf_vid": _vid("nfInstance", lipfNfId) if lipfNfId else None,
        "activated_at": x1ProvisionedAt,
        "deactivated_at": None, "deactivation_reason": None,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_li_target", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "targetId": t_id, "status": row["status"]}


def task_telecom_li_target_deactivate(
    targetId: str = "", deactivationReason: str = "", deactivatedAt: str = "",
    licfNfId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"targetId": targetId, "deactivationReason": deactivationReason,
               "deactivatedAt": deactivatedAt, "callerDid": callerDid}
    _require(payload, ["targetId", "deactivationReason", "deactivatedAt"])
    if deactivationReason not in DEACT_REASONS:
        raise ValueError(f"unsupported deactivationReason: {deactivationReason}")
    vid = _vid("liTarget", targetId)
    if not dryRun:
        get_kotoba_client().insert_row(
            "vertex_telecom_li_target",
            {
                "vertex_id": vid,
                "deactivated_at": deactivatedAt,
                "deactivation_reason": deactivationReason,
                "status": "deactivated",
            },
        )
    return {"ok": True, "vertexId": vid, "targetId": targetId, "status": "deactivated"}


def task_telecom_li_iri_deliver(
    targetId: str = "", eventKind: str = "", eventVid: str = "",
    x2Sequence: int = 0, df2NfId: str = "", lemfId: str = "",
    payloadHash: str = "", observedAt: str = "",
    iriId: str = "", payloadSize: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"targetId": targetId, "eventKind": eventKind, "eventVid": eventVid,
               "x2Sequence": x2Sequence, "df2NfId": df2NfId, "lemfId": lemfId,
               "payloadHash": payloadHash, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["targetId", "eventKind", "eventVid", "x2Sequence",
                       "df2NfId", "lemfId", "payloadHash", "observedAt"])
    if eventKind not in IRI_EVENT_KINDS:
        raise ValueError(f"unsupported eventKind: {eventKind}")
    seq = int(x2Sequence)
    if seq <= 0:
        raise ValueError("x2Sequence must be > 0")
    if not (payloadHash.startswith("sha256:") or payloadHash.startswith("sha384:") or payloadHash.startswith("sha512:")):
        raise ValueError("payloadHash must be prefixed with sha256:|sha384:|sha512:")
    i_id = iriId.strip() or _new_id("iri", targetId, eventKind, seq)
    vid = _vid("liIriDelivery", i_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "iri_id": i_id,
        "target_vid": _vid("liTarget", targetId),
        "event_kind": eventKind, "event_vid": eventVid,
        "x2_sequence": seq,
        "df2_nf_vid": _vid("nfInstance", df2NfId),
        "lemf_id": lemfId,
        "payload_hash": payloadHash,
        "payload_size": int(payloadSize) if payloadSize is not None else None,
        "observed_at": observedAt,
        "ack_status": None, "acked_at": None,
        "status": "delivered",
        **_audit(payload),
    }
    _insert("vertex_telecom_li_iri_delivery", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "iriId": i_id, "status": row["status"]}


def task_telecom_li_cc_deliver(
    targetId: str = "", contentKind: str = "", x3Sequence: int = 0,
    df3NfId: str = "", lemfId: str = "", payloadHash: str = "",
    observedAt: str = "",
    ccId: str = "", payloadSize: int | None = None, encryptionRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"targetId": targetId, "contentKind": contentKind,
               "x3Sequence": x3Sequence, "df3NfId": df3NfId, "lemfId": lemfId,
               "payloadHash": payloadHash, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["targetId", "contentKind", "x3Sequence", "df3NfId",
                       "lemfId", "payloadHash", "observedAt"])
    if contentKind not in CC_KINDS:
        raise ValueError(f"unsupported contentKind: {contentKind}")
    seq = int(x3Sequence)
    if seq <= 0:
        raise ValueError("x3Sequence must be > 0")
    if not (payloadHash.startswith("sha256:") or payloadHash.startswith("sha384:") or payloadHash.startswith("sha512:")):
        raise ValueError("payloadHash must be prefixed with sha256:|sha384:|sha512:")
    _require_vault_ref(encryptionRef, "encryptionRef")
    c_id = ccId.strip() or _new_id("cc", targetId, contentKind, seq)
    vid = _vid("liCcDelivery", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "cc_id": c_id,
        "target_vid": _vid("liTarget", targetId),
        "content_kind": contentKind,
        "x3_sequence": seq,
        "df3_nf_vid": _vid("nfInstance", df3NfId),
        "lemf_id": lemfId,
        "payload_hash": payloadHash,
        "payload_size": int(payloadSize) if payloadSize is not None else None,
        "encryption_ref": encryptionRef or None,
        "observed_at": observedAt,
        "ack_status": None, "acked_at": None,
        "status": "delivered",
        **_audit(payload),
    }
    _insert("vertex_telecom_li_cc_delivery", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "ccId": c_id, "status": row["status"]}


def task_telecom_li_delivery_ack(
    deliveryKind: str = "", deliveryVid: str = "", lemfId: str = "",
    ackResult: str = "", ackedAt: str = "",
    ackId: str = "", ackCode: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"deliveryKind": deliveryKind, "deliveryVid": deliveryVid,
               "lemfId": lemfId, "ackResult": ackResult, "ackedAt": ackedAt,
               "callerDid": callerDid}
    _require(payload, ["deliveryKind", "deliveryVid", "lemfId", "ackResult", "ackedAt"])
    if deliveryKind not in DELIVERY_KINDS:
        raise ValueError(f"unsupported deliveryKind: {deliveryKind}")
    if ackResult not in ACK_RESULTS:
        raise ValueError(f"unsupported ackResult: {ackResult}")
    a_id = ackId.strip() or _new_id("ack", deliveryKind, deliveryVid, ackedAt)
    vid = _vid("liDeliveryAck", a_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "ack_id": a_id,
        "delivery_kind": deliveryKind,
        "delivery_vid": deliveryVid,
        "lemf_id": lemfId,
        "ack_result": ackResult,
        "ack_code": ackCode or None,
        "acked_at": ackedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_li_delivery_ack", row, dry_run=dryRun)
    if not dryRun:
        target_table = "vertex_telecom_li_iri_delivery" if deliveryKind == "iri" else "vertex_telecom_li_cc_delivery"
        get_kotoba_client().insert_row(
            target_table,
            {
                "vertex_id": deliveryVid,
                "ack_status": ackResult,
                "acked_at": ackedAt,
            },
        )
    return {"ok": True, "vertexId": vid, "ackId": a_id, "status": row["status"]}


def task_telecom_li_audit_access(
    accessKind: str = "", accessor: str = "", accessorRole: str = "",
    recordKind: str = "", recordVid: str = "", observedAt: str = "",
    auditId: str = "", warrantId: str = "", targetId: str = "",
    justification: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"accessKind": accessKind, "accessor": accessor,
               "accessorRole": accessorRole, "recordKind": recordKind,
               "recordVid": recordVid, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["accessKind", "accessor", "accessorRole",
                       "recordKind", "recordVid", "observedAt"])
    if accessKind not in ACCESS_KINDS:
        raise ValueError(f"unsupported accessKind: {accessKind}")
    if accessorRole not in ACCESSOR_ROLES:
        raise ValueError(f"unsupported accessorRole: {accessorRole}")
    if recordKind not in RECORD_KINDS:
        raise ValueError(f"unsupported recordKind: {recordKind}")
    a_id = auditId.strip() or _new_id("liaud", accessor, recordVid, observedAt)
    vid = _vid("liAccessAudit", a_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "audit_id": a_id,
        "warrant_vid": _vid("liWarrant", warrantId) if warrantId else None,
        "target_vid": _vid("liTarget", targetId) if targetId else None,
        "access_kind": accessKind,
        "accessor_hash": _hash_id(accessor),
        "accessor_role": accessorRole,
        "justification": justification or None,
        "record_kind": recordKind,
        "record_vid": recordVid,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_li_access_audit", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "auditId": a_id, "status": row["status"]}


def task_telecom_li_warrant_close(
    warrantId: str = "", closureReason: str = "", closedAt: str = "",
    retentionUntil: str = "",
    finalReportRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"warrantId": warrantId, "closureReason": closureReason,
               "closedAt": closedAt, "retentionUntil": retentionUntil,
               "callerDid": callerDid}
    _require(payload, ["warrantId", "closureReason", "closedAt", "retentionUntil"])
    if closureReason not in CLOSURE_REASONS:
        raise ValueError(f"unsupported closureReason: {closureReason}")
    _require_vault_ref(finalReportRef, "finalReportRef")
    vid = _vid("liWarrant", warrantId)
    if not dryRun:
        get_kotoba_client().insert_row(
            "vertex_telecom_li_warrant",
            {
                "vertex_id": vid,
                "closed_at": closedAt,
                "closure_reason": closureReason,
                "retention_until": retentionUntil,
                "final_report_ref": finalReportRef or None,
                "status": "closed",
            },
        )
    return {"ok": True, "vertexId": vid, "warrantId": warrantId, "status": "closed"}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.li.warrant.register",  single_value=False, timeout_ms=timeout_ms)(task_telecom_li_warrant_register)
    worker.task(task_type="telecom.li.target.activate",   single_value=False, timeout_ms=timeout_ms)(task_telecom_li_target_activate)
    worker.task(task_type="telecom.li.target.deactivate", single_value=False, timeout_ms=timeout_ms)(task_telecom_li_target_deactivate)
    worker.task(task_type="telecom.li.iri.deliver",       single_value=False, timeout_ms=timeout_ms)(task_telecom_li_iri_deliver)
    worker.task(task_type="telecom.li.cc.deliver",        single_value=False, timeout_ms=timeout_ms)(task_telecom_li_cc_deliver)
    worker.task(task_type="telecom.li.delivery.ack",      single_value=False, timeout_ms=timeout_ms)(task_telecom_li_delivery_ack)
    worker.task(task_type="telecom.li.audit.access",      single_value=False, timeout_ms=timeout_ms)(task_telecom_li_audit_access)
    worker.task(task_type="telecom.li.warrant.close",     single_value=False, timeout_ms=timeout_ms)(task_telecom_li_warrant_close)
