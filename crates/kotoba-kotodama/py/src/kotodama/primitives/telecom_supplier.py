"""telecom Phase 3 primitives — Supplier/Partner domain.

Eight BPMN service tasks bound to the telecom actor:

  - telecom.interconnect.register
  - telecom.roaming.partner
  - telecom.roaming.tapFile
  - telecom.roaming.settle
  - telecom.interconnect.cdr
  - telecom.numberRange.register
  - telecom.mnp.portIn
  - telecom.mnp.portOut

settleRoamingInvoice aggregates per-direction inbound (RECEIVABLE — peer
charges us) and outbound (PAYABLE — we charge peer) TAP files over the
period and writes a `vertex_telecom_roaming_invoice` row.

MSISDN values are persisted as `sha256:` hashes; raw values must remain
out-of-band per ADR-0018 PII tier rules.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, date, datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.supplier"

PEER_KINDS = {"mno", "mvno", "fixed", "isp", "transit"}
TAP_FILE_TYPES = {"tap", "rap", "iot", "nrtrde"}
SETTLE_DIRECTIONS = {"receivable", "payable", "net"}
INTERCONNECT_DIRECTIONS = {"originating", "terminating", "transit"}
USAGE_TYPES = {"voice", "sms", "data", "iot"}


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


def _parse_date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return date.fromisoformat(value[:10])


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


def task_telecom_interconnect_register(
    peerOrgId: str = "", peerKind: str = "", jurisdiction: str = "",
    settlementCurrency: str = "", validFrom: str = "", validUntil: str = "",
    agreementId: str = "", rateCardRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {
        "peerOrgId": peerOrgId, "peerKind": peerKind, "jurisdiction": jurisdiction,
        "settlementCurrency": settlementCurrency, "validFrom": validFrom,
        "validUntil": validUntil, "callerDid": callerDid,
    }
    _require(payload, ["peerOrgId", "peerKind", "jurisdiction", "settlementCurrency", "validFrom", "validUntil"])
    if peerKind not in PEER_KINDS:
        raise ValueError(f"unsupported peerKind: {peerKind}")
    a_id = agreementId.strip() or _new_id("agr", peerOrgId, jurisdiction, validFrom)
    vid = _vid("interconnectAgreement", a_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "agreement_id": a_id, "peer_org_id": peerOrgId, "peer_kind": peerKind,
        "jurisdiction": jurisdiction, "settlement_currency": settlementCurrency,
        "rate_card_ref": rateCardRef or None,
        "valid_from": validFrom, "valid_until": validUntil,
        "status": "active", **_audit(payload),
    }
    _insert("vertex_telecom_interconnect_agreement", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "agreementId": a_id, "status": row["status"]}


def task_telecom_roaming_partner(
    peerOrgId: str = "", tadigCode: str = "", agreementId: str = "",
    partnerId: str = "", plmnId: str = "", sccpGtPrefix: str = "", imsiPrefix: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"peerOrgId": peerOrgId, "tadigCode": tadigCode, "agreementId": agreementId, "callerDid": callerDid}
    _require(payload, ["peerOrgId", "tadigCode", "agreementId"])
    p_id = partnerId.strip() or _new_id("part", tadigCode, peerOrgId)
    vid = _vid("roamingPartner", p_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "partner_id": p_id, "peer_org_id": peerOrgId,
        "tadig_code": tadigCode,
        "plmn_id": plmnId or None,
        "sccp_gt_prefix": sccpGtPrefix or None,
        "imsi_prefix": imsiPrefix or None,
        "agreement_vid": _vid("interconnectAgreement", agreementId),
        "status": "active", **_audit(payload),
    }
    _insert("vertex_telecom_roaming_partner", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "partnerId": p_id, "status": row["status"]}


def task_telecom_roaming_tap_file(
    partnerId: str = "", fileType: str = "", fileSequence: int = 0,
    transferDate: str = "", totalCharge: float = 0.0, currency: str = "",
    tapFileId: str = "", voiceUnits: float | None = None,
    smsUnits: float | None = None, dataUnits: float | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"partnerId": partnerId, "fileType": fileType, "fileSequence": fileSequence,
               "transferDate": transferDate, "totalCharge": totalCharge, "currency": currency,
               "callerDid": callerDid}
    _require(payload, ["partnerId", "fileType", "fileSequence", "transferDate", "currency"])
    if fileType not in TAP_FILE_TYPES:
        raise ValueError(f"unsupported fileType: {fileType}")
    seq = int(fileSequence)
    if seq <= 0:
        raise ValueError("fileSequence must be > 0")
    f_id = tapFileId.strip() or _new_id("tap", partnerId, fileType, seq, transferDate)
    vid = _vid("tapFile", f_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "tap_file_id": f_id,
        "partner_vid": _vid("roamingPartner", partnerId),
        "file_type": fileType, "file_sequence": seq,
        "transfer_date": transferDate,
        "voice_units": float(voiceUnits) if voiceUnits is not None else None,
        "sms_units": float(smsUnits) if smsUnits is not None else None,
        "data_units": float(dataUnits) if dataUnits is not None else None,
        "total_charge": float(totalCharge), "currency": currency,
        "status": "received", **_audit(payload),
    }
    _insert("vertex_telecom_tap_file", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "tapFileId": f_id, "status": row["status"]}


def task_telecom_roaming_settle(
    partnerId: str = "", periodStart: str = "", periodEnd: str = "", direction: str = "",
    invoiceId: str = "", currency: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"partnerId": partnerId, "periodStart": periodStart, "periodEnd": periodEnd,
               "direction": direction, "callerDid": callerDid}
    _require(payload, ["partnerId", "periodStart", "periodEnd", "direction"])
    if direction not in SETTLE_DIRECTIONS:
        raise ValueError(f"unsupported direction: {direction}")
    ps = _parse_date(periodStart, "periodStart")
    pe = _parse_date(periodEnd, "periodEnd")
    if pe <= ps:
        raise ValueError("periodEnd must be after periodStart")
    partner_vid = _vid("roamingPartner", partnerId)
    inv_id = invoiceId.strip() or _new_id("rinv", partnerId, ps.isoformat(), pe.isoformat(), direction)
    vid = _vid("roamingInvoice", inv_id)
    receivable = 0.0
    payable = 0.0
    resolved_currency = currency or "USD"
    if not dryRun:
        # R0: Multi-predicate WHERE and aggregation are handled in Python.
        tap_files = get_kotoba_client().select_where(
            "vertex_telecom_tap_file", "partner_vid", partner_vid
        )
        currencies = set()
        for r in tap_files:
            file_transfer_date = _parse_date(r["transfer_date"], "transfer_date")
            if (ps <= file_transfer_date < pe) and r["status"] == "received":
                charge = float(r["total_charge"] or 0.0)
                if r["file_type"] in ("tap", "iot"):
                    receivable += charge
                elif r["file_type"] in ("rap", "nrtrde"):
                    payable += charge
                if r["currency"]:
                    currencies.add(r["currency"])

        if currencies:
            resolved_currency = list(currencies)[0] # Just pick one if multiple, as per original MAX behavior
        else:
            resolved_currency = currency or "USD"

    net = receivable - payable
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "invoice_id": inv_id, "partner_vid": partner_vid,
        "period_start": ps.isoformat(), "period_end": pe.isoformat(),
        "direction": direction, "currency": resolved_currency,
        "receivable_amount": round(receivable, 4),
        "payable_amount": round(payable, 4),
        "net_amount": round(net, 4),
        "status": "issued", **_audit(payload),
    }
    _insert("vertex_telecom_roaming_invoice", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "invoiceId": inv_id,
            "netAmount": row["net_amount"], "status": row["status"]}


def task_telecom_interconnect_cdr(
    agreementId: str = "", partnerId: str = "", direction: str = "",
    usageType: str = "", units: float = 0.0, startedAt: str = "",
    cdrId: str = "", unitOfMeasure: str = "",
    originatingMsisdn: str = "", terminatingMsisdn: str = "",
    endedAt: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"agreementId": agreementId, "partnerId": partnerId, "direction": direction,
               "usageType": usageType, "units": units, "startedAt": startedAt,
               "callerDid": callerDid}
    _require(payload, ["agreementId", "partnerId", "direction", "usageType", "startedAt"])
    if direction not in INTERCONNECT_DIRECTIONS:
        raise ValueError(f"unsupported direction: {direction}")
    if usageType not in USAGE_TYPES:
        raise ValueError(f"unsupported usageType: {usageType}")
    units_f = float(units)
    if units_f < 0:
        raise ValueError("units must be non-negative")
    c_id = cdrId.strip() or _new_id("icdr", agreementId, partnerId, direction, usageType, startedAt)
    vid = _vid("interconnectCdr", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "cdr_id": c_id,
        "agreement_vid": _vid("interconnectAgreement", agreementId),
        "partner_vid": _vid("roamingPartner", partnerId),
        "direction": direction, "usage_type": usageType,
        "units": units_f, "unit_of_measure": unitOfMeasure or None,
        "originating_msisdn_hash": _hash_id(originatingMsisdn) if originatingMsisdn else None,
        "terminating_msisdn_hash": _hash_id(terminatingMsisdn) if terminatingMsisdn else None,
        "started_at": startedAt, "ended_at": endedAt or None,
        "status": "recorded", **_audit(payload),
    }
    _insert("vertex_telecom_interconnect_cdr", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "cdrId": c_id, "status": row["status"]}


def task_telecom_number_range_register(
    jurisdiction: str = "", countryCode: str = "",
    startMsisdn: str = "", endMsisdn: str = "", allocatedAt: str = "",
    rangeId: str = "", regulatorAllocationId: str = "", plmnId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"jurisdiction": jurisdiction, "countryCode": countryCode,
               "startMsisdn": startMsisdn, "endMsisdn": endMsisdn,
               "allocatedAt": allocatedAt, "callerDid": callerDid}
    _require(payload, ["jurisdiction", "countryCode", "startMsisdn", "endMsisdn", "allocatedAt"])
    if startMsisdn >= endMsisdn:
        raise ValueError("endMsisdn must be > startMsisdn")
    r_id = rangeId.strip() or _new_id("nrange", jurisdiction, startMsisdn, endMsisdn)
    vid = _vid("numberRange", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "range_id": r_id, "jurisdiction": jurisdiction,
        "country_code": countryCode,
        "start_msisdn": startMsisdn, "end_msisdn": endMsisdn,
        "regulator_allocation_id": regulatorAllocationId or None,
        "allocated_at": allocatedAt,
        "plmn_id": plmnId or None,
        "status": "allocated", **_audit(payload),
    }
    _insert("vertex_telecom_number_range", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "rangeId": r_id, "status": row["status"]}


def _mnp_payload(direction: str, msisdn: str, subscriberId: str,
                 counterpartPartnerId: str, requestedAt: str,
                 requestId: str, scheduledCutoverAt: str, authCode: str,
                 callerDid: str, dryRun: bool) -> dict[str, Any]:
    payload = {"msisdn": msisdn, "subscriberId": subscriberId,
               "counterpartPartnerId": counterpartPartnerId,
               "requestedAt": requestedAt, "callerDid": callerDid}
    _require(payload, ["msisdn", "subscriberId", "counterpartPartnerId", "requestedAt"])
    r_id = requestId.strip() or _new_id("mnp", direction, msisdn, requestedAt)
    vid = _vid("mnpRequest", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "request_id": r_id, "direction": direction,
        "msisdn_hash": _hash_id(msisdn),
        "subscriber_vid": _vid("subscriber", subscriberId),
        "counterpart_partner_vid": _vid("roamingPartner", counterpartPartnerId),
        "requested_at": requestedAt,
        "scheduled_cutover_at": scheduledCutoverAt or None,
        "completed_at": None,
        "auth_code_hash": _hash_id(authCode) if authCode else None,
        "status": "requested", **_audit(payload),
    }
    _insert("vertex_telecom_mnp_request", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "requestId": r_id, "status": row["status"]}


def task_telecom_mnp_port_in(
    msisdn: str = "", subscriberId: str = "", donorPartnerId: str = "",
    requestedAt: str = "", authCode: str = "",
    requestId: str = "", scheduledCutoverAt: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    if not authCode:
        raise ValueError("authCode is required for portIn")
    return _mnp_payload(
        "in", msisdn, subscriberId, donorPartnerId, requestedAt,
        requestId, scheduledCutoverAt, authCode, callerDid, dryRun,
    )


def task_telecom_mnp_port_out(
    msisdn: str = "", subscriberId: str = "", recipientPartnerId: str = "",
    requestedAt: str = "", authCodeIssued: str = "",
    requestId: str = "", scheduledCutoverAt: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    return _mnp_payload(
        "out", msisdn, subscriberId, recipientPartnerId, requestedAt,
        requestId, scheduledCutoverAt, authCodeIssued, callerDid, dryRun,
    )


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.interconnect.register", single_value=False, timeout_ms=timeout_ms)(task_telecom_interconnect_register)
    worker.task(task_type="telecom.roaming.partner",       single_value=False, timeout_ms=timeout_ms)(task_telecom_roaming_partner)
    worker.task(task_type="telecom.roaming.tapFile",       single_value=False, timeout_ms=timeout_ms * 2)(task_telecom_roaming_tap_file)
    worker.task(task_type="telecom.roaming.settle",        single_value=False, timeout_ms=timeout_ms * 2)(task_telecom_roaming_settle)
    worker.task(task_type="telecom.interconnect.cdr",      single_value=False, timeout_ms=timeout_ms)(task_telecom_interconnect_cdr)
    worker.task(task_type="telecom.numberRange.register",  single_value=False, timeout_ms=timeout_ms)(task_telecom_number_range_register)
    worker.task(task_type="telecom.mnp.portIn",            single_value=False, timeout_ms=timeout_ms)(task_telecom_mnp_port_in)
    worker.task(task_type="telecom.mnp.portOut",           single_value=False, timeout_ms=timeout_ms)(task_telecom_mnp_port_out)
