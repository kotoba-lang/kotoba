"""telecom Phase 1 primitives — eTOM Customer + Service Provisioning core.

Six BPMN service tasks registered via ADR-0056 BPMN-as-actor:

  - telecom.subscriber.onboard
  - telecom.sim.activate
  - telecom.service.provision
  - telecom.usage.record
  - telecom.billing.cycle
  - telecom.sla.escalate

PII split per ADR-0018: AT Repo + main subscriber row hold hashed MSISDN/IMSI
only; raw name / MSISDN / IMSI live in vertex_telecom_subscriber_pii at
sensitivity_ord=3. Domain writes follow ADR-0036 (Worker-direct kotoba Datom log
INSERT, no PDS createRecord for com.etzhayyim.apps.telecom.*).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, date, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom"

# Phase 1 coarse rate card (cents per unit). Replaced by per-plan tariff
# vertex in Phase 2.
RATE_CARD = {
    "voice": 0.02,        # per second
    "sms": 0.05,          # per message
    "data": 0.000_000_01, # per byte (~ 0.01 / MB)
    "iot": 0.001,         # per event
}

USAGE_TYPES = {"voice", "sms", "data", "iot"}
SERVICE_TYPES = {"voice", "sms", "data", "iot", "fixed_line", "fiber"}
SEVERITIES = {"minor", "major", "critical"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _today_iso() -> str:
    return date.today().isoformat()


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
    missing = [f for f in fields if not str(payload.get(f, "")).strip()]
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


def _vid_subscriber(subscriber_id: str) -> str:
    return f"at://did:web:telecom.etzhayyim.com/com.etzhayyim.apps.telecom.subscriber/{subscriber_id}"


def _vid_sim(sim_id: str) -> str:
    return f"at://did:web:telecom.etzhayyim.com/com.etzhayyim.apps.telecom.sim/{sim_id}"


def _vid_service(service_id: str) -> str:
    return f"at://did:web:telecom.etzhayyim.com/com.etzhayyim.apps.telecom.service/{service_id}"


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_subscriber_onboard(
    customerName: str = "",
    msisdn: str = "",
    imsi: str = "",
    kycStatus: str = "",
    planId: str = "",
    subscriberId: str = "",
    callerDid: str = "",
    asOf: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    payload = {
        "customerName": customerName, "msisdn": msisdn, "imsi": imsi,
        "kycStatus": kycStatus, "planId": planId, "subscriberId": subscriberId,
        "callerDid": callerDid, "asOf": asOf,
    }
    _require(payload, ["customerName", "msisdn", "kycStatus", "planId"])
    sub_id = subscriberId.strip() or _new_id("sub", msisdn)
    vid = _vid_subscriber(sub_id)
    audit = _audit(payload)
    main_row = {
        "vertex_id": vid,
        "owner_did": _caller(payload),
        "subscriber_id": sub_id,
        "msisdn_hash": _hash_id(msisdn),
        "imsi_hash": _hash_id(imsi) if imsi else None,
        "kyc_status": kycStatus,
        "plan_id": planId,
        "status": "active" if kycStatus == "verified" else "pending",
        "onboarded_at": _now_iso(),
        **audit,
    }
    _insert("vertex_telecom_subscriber", main_row, dry_run=dryRun)
    pii_row = {
        "vertex_id": f"{vid}/pii",
        "owner_did": _caller(payload),
        "subscriber_vid": vid,
        "customer_name": customerName,
        "msisdn": msisdn,
        "imsi": imsi or None,
        **audit,
        "sensitivity_ord": 3,
    }
    _insert("vertex_telecom_subscriber_pii", pii_row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "subscriberId": sub_id, "status": main_row["status"]}


def task_telecom_sim_activate(
    iccid: str = "",
    subscriberId: str = "",
    msisdn: str = "",
    imsi: str = "",
    simType: str = "physical",
    simId: str = "",
    callerDid: str = "",
    asOf: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"iccid": iccid, "subscriberId": subscriberId, "callerDid": callerDid}
    _require(payload, ["iccid", "subscriberId"])
    sid = simId.strip() or _new_id("sim", iccid)
    vid = _vid_sim(sid)
    row = {
        "vertex_id": vid,
        "owner_did": _caller(payload),
        "sim_id": sid,
        "iccid_hash": _hash_id(iccid),
        "subscriber_vid": _vid_subscriber(subscriberId),
        "sim_type": simType,
        "status": "active",
        "activated_at": _now_iso(),
        **_audit(payload),
    }
    _insert("vertex_telecom_sim", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "simId": sid, "status": row["status"]}


def task_telecom_service_provision(
    subscriberId: str = "",
    serviceType: str = "",
    planId: str = "",
    simId: str = "",
    qosProfile: str = "",
    apn: str = "",
    serviceId: str = "",
    callerDid: str = "",
    asOf: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"subscriberId": subscriberId, "serviceType": serviceType, "planId": planId, "callerDid": callerDid}
    _require(payload, ["subscriberId", "serviceType", "planId"])
    if serviceType not in SERVICE_TYPES:
        raise ValueError(f"unsupported serviceType: {serviceType}")
    sv_id = serviceId.strip() or _new_id("svc", subscriberId, serviceType, planId)
    vid = _vid_service(sv_id)
    row = {
        "vertex_id": vid,
        "owner_did": _caller(payload),
        "service_id": sv_id,
        "subscriber_vid": _vid_subscriber(subscriberId),
        "sim_vid": _vid_sim(simId) if simId else None,
        "service_type": serviceType,
        "plan_id": planId,
        "qos_profile": qosProfile or None,
        "apn": apn or None,
        "status": "active",
        "provisioned_at": _now_iso(),
        **_audit(payload),
    }
    _insert("vertex_telecom_service", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "serviceId": sv_id, "status": row["status"]}


def task_telecom_usage_record(
    subscriberId: str = "",
    serviceId: str = "",
    usageType: str = "",
    units: float = 0.0,
    unitOfMeasure: str = "",
    peerMsisdn: str = "",
    startedAt: str = "",
    endedAt: str = "",
    cdrId: str = "",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    payload = {
        "subscriberId": subscriberId, "serviceId": serviceId,
        "usageType": usageType, "units": units, "startedAt": startedAt,
        "callerDid": callerDid,
    }
    _require(payload, ["subscriberId", "serviceId", "usageType", "startedAt"])
    if usageType not in USAGE_TYPES:
        raise ValueError(f"unsupported usageType: {usageType}")
    units_f = float(units)
    if units_f < 0:
        raise ValueError("units must be non-negative")
    cdr_id = cdrId.strip() or _new_id("cdr", subscriberId, serviceId, usageType, startedAt)
    vid = f"at://did:web:telecom.etzhayyim.com/com.etzhayyim.apps.telecom.cdr/{cdr_id}"
    row = {
        "vertex_id": vid,
        "owner_did": _caller(payload),
        "cdr_id": cdr_id,
        "subscriber_vid": _vid_subscriber(subscriberId),
        "service_vid": _vid_service(serviceId),
        "usage_type": usageType,
        "units": units_f,
        "unit_of_measure": unitOfMeasure or None,
        "peer_msisdn_hash": _hash_id(peerMsisdn) if peerMsisdn else None,
        "started_at": startedAt,
        "ended_at": endedAt or None,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_cdr", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "cdrId": cdr_id, "status": row["status"]}


def task_telecom_billing_cycle(
    subscriberId: str = "",
    periodStart: str = "",
    periodEnd: str = "",
    cycleId: str = "",
    invoiceId: str = "",
    currency: str = "JPY",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"subscriberId": subscriberId, "periodStart": periodStart, "periodEnd": periodEnd, "callerDid": callerDid}
    _require(payload, ["subscriberId", "periodStart", "periodEnd"])
    ps = _parse_date(periodStart, "periodStart")
    pe = _parse_date(periodEnd, "periodEnd")
    if pe <= ps:
        raise ValueError("periodEnd must be after periodStart")
    sub_vid = _vid_subscriber(subscriberId)
    cycle = cycleId.strip() or f"{ps.isoformat()}_{pe.isoformat()}"
    inv_id = invoiceId.strip() or _new_id("inv", subscriberId, cycle)
    vid = f"at://did:web:telecom.etzhayyim.com/com.etzhayyim.apps.telecom.invoice/{inv_id}"
    totals = {k: 0.0 for k in RATE_CARD}
    if not dryRun:
        # R0: Multi-predicate filter and aggregation in Python
        cdr_records = get_kotoba_client().select_where(
            "vertex_telecom_cdr", "subscriber_vid", sub_vid, limit=2000
        )
        for record in cdr_records:
            started_at_str = record.get("started_at")
            status = record.get("status")
            if (
                started_at_str
                and status == "recorded"
                and ps.isoformat() <= started_at_str < pe.isoformat()
            ):
                usage_type = record.get("usage_type")
                units = record.get("units", 0.0)
                if usage_type in totals:
                    totals[usage_type] += float(units)
    total = sum(totals.get(k, 0.0) * RATE_CARD[k] for k in RATE_CARD)
    row = {
        "vertex_id": vid,
        "owner_did": _caller(payload),
        "invoice_id": inv_id,
        "cycle_id": cycle,
        "subscriber_vid": sub_vid,
        "period_start": ps.isoformat(),
        "period_end": pe.isoformat(),
        "currency": currency or "JPY",
        "total_amount": round(total, 4),
        "voice_units": totals.get("voice", 0.0),
        "sms_units": totals.get("sms", 0.0),
        "data_units": totals.get("data", 0.0),
        "status": "issued",
        **_audit(payload),
    }
    _insert("vertex_telecom_invoice", row, dry_run=dryRun)
    return {
        "ok": True, "vertexId": vid, "invoiceId": inv_id,
        "totalAmount": row["total_amount"], "status": row["status"],
    }


def task_telecom_sla_escalate(
    serviceId: str = "",
    breachType: str = "",
    severity: str = "",
    observedAt: str = "",
    metric: str = "",
    observedValue: float | None = None,
    slaThreshold: float | None = None,
    breachId: str = "",
    ticketId: str = "",
    callerDid: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"serviceId": serviceId, "breachType": breachType, "severity": severity, "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["serviceId", "breachType", "severity", "observedAt"])
    if severity not in SEVERITIES:
        raise ValueError(f"unsupported severity: {severity}")
    br_id = breachId.strip() or _new_id("brc", serviceId, observedAt, breachType)
    tkt = ticketId.strip() or _new_id("tkt", br_id)
    vid = f"at://did:web:telecom.etzhayyim.com/com.etzhayyim.apps.telecom.slaBreach/{br_id}"
    row = {
        "vertex_id": vid,
        "owner_did": _caller(payload),
        "breach_id": br_id,
        "service_vid": _vid_service(serviceId),
        "breach_type": breachType,
        "severity": severity,
        "metric": metric or None,
        "observed_value": float(observedValue) if observedValue is not None else None,
        "sla_threshold": float(slaThreshold) if slaThreshold is not None else None,
        "observed_at": observedAt,
        "ticket_id": tkt,
        "status": "open",
        **_audit(payload),
    }
    _insert("vertex_telecom_sla_breach", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "breachId": br_id, "ticketId": tkt, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.subscriber.onboard", single_value=False, timeout_ms=timeout_ms)(task_telecom_subscriber_onboard)
    worker.task(task_type="telecom.sim.activate",       single_value=False, timeout_ms=timeout_ms)(task_telecom_sim_activate)
    worker.task(task_type="telecom.service.provision",  single_value=False, timeout_ms=timeout_ms)(task_telecom_service_provision)
    worker.task(task_type="telecom.usage.record",       single_value=False, timeout_ms=timeout_ms)(task_telecom_usage_record)
    worker.task(task_type="telecom.billing.cycle",      single_value=False, timeout_ms=timeout_ms * 2)(task_telecom_billing_cycle)
    worker.task(task_type="telecom.sla.escalate",       single_value=False, timeout_ms=timeout_ms)(task_telecom_sla_escalate)
