"""Airline Safety Management System XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
APP_DID = "did:web:air-sms.etzhayyim.com"
ACTOR_SLUG = "air-sms"


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vid(kind: str, key: str) -> str:
    safe_key = key.replace("/", "_").replace(" ", "_")[:160] or uuid.uuid4().hex
    return f"air-sms:{kind}:{safe_key}"


def _new_vid(kind: str) -> str:
    return f"air-sms:{kind}:{uuid.uuid4().hex}"


def submit_safety_report(
    callerDid: str = "",
    reportRef: str = "",
    reporterDid: str = "",
    category: str = "",
    occurrence: str = "",
    station: str = "",
    flightNo: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("safety-report", reportRef or occurrence or uuid.uuid4().hex[:16])
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sms_safety_report", {
        "vertex_id": vertex_id,
        "report_ref": reportRef or vertex_id,
        "reporter_did": reporterDid or callerDid or APP_DID,
        "category": category,
        "occurrence": occurrence or '',
        "station": station or '',
        "flight_no": flightNo or '',
        "status": 'submitted',
        "submitted_at": now,
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 2,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "reportRef": reportRef or vertex_id,
        "category": category,
        "reportStatus": "submitted",
    }


def assess_risk(
    callerDid: str = "",
    reportRef: str = "",
    likelihood: int = 1,
    severity: int = 1,
    mitigations: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("risk-assess")
    now = _now()
    risk_score = int(likelihood) * int(severity)
    if risk_score >= 15:
        risk_level = "high"
    elif risk_score >= 8:
        risk_level = "medium"
    else:
        risk_level = "low"
    get_kotoba_client().insert_row("vertex_air_sms_safety_report", {
        "vertex_id": vertex_id,
        "report_ref": reportRef,
        "likelihood": int(likelihood),
        "severity": int(severity),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "mitigations": mitigations or '',
        "status": 'assessed',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 2,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "reportRef": reportRef,
        "riskScore": risk_score,
        "riskLevel": risk_level,
        "likelihood": int(likelihood),
        "severity": int(severity),
    }


def record_iosa_finding(
    callerDid: str = "",
    auditRef: str = "",
    findingRef: str = "",
    iosaCategory: str = "",
    findingType: str = "",
    dueDate: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("iosa-finding", findingRef or f"{auditRef}:{iosaCategory}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sms_safety_report", {
        "vertex_id": vertex_id,
        "audit_ref": auditRef,
        "finding_ref": findingRef or vertex_id,
        "iosa_category": iosaCategory,
        "finding_type": findingType or '',
        "due_date": dueDate or now[:10],
        "status": 'open',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 2,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "auditRef": auditRef,
        "findingRef": findingRef or vertex_id,
        "iosaCategory": iosaCategory,
        "findingStatus": "open",
    }


def file_regulatory(
    callerDid: str = "",
    regulatoryBody: str = "",
    filingType: str = "",
    filingRef: str = "",
    periodStart: str = "",
    periodEnd: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("regulatory", f"{regulatoryBody}:{filingType}:{filingRef or periodStart}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sms_safety_report", {
        "vertex_id": vertex_id,
        "regulatory_body": regulatoryBody,
        "filing_type": filingType,
        "filing_ref": filingRef or vertex_id,
        "period_start": periodStart or now[:10],
        "period_end": periodEnd or now[:10],
        "status": 'filed',
        "filed_at": now,
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 2,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "regulatoryBody": regulatoryBody,
        "filingRef": filingRef or vertex_id,
        "filingStatus": "filed",
    }


def report_occurrence(
    callerDid: str = "",
    occurrenceRef: str = "",
    occurrenceType: str = "",
    occurrenceDate: str = "",
    station: str = "",
    severity: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("occurrence", occurrenceRef or occurrenceType)
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sms_safety_report", {
        "vertex_id": vertex_id,
        "occurrence_ref": occurrenceRef or vertex_id,
        "occurrence_type": occurrenceType,
        "occurrence_date": occurrenceDate or now[:10],
        "station": station or '',
        "severity": severity or 'low',
        "status": 'reported',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 2,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "occurrenceRef": occurrenceRef or vertex_id,
        "occurrenceType": occurrenceType,
        "severity": severity or "low",
    }


def distribute_bulletin(
    callerDid: str = "",
    bulletinRef: str = "",
    bulletinType: str = "",
    subject: str = "",
    targetAudience: str = "",
    effectiveDate: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("bulletin", bulletinRef or bulletinType)
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sms_safety_report", {
        "vertex_id": vertex_id,
        "bulletin_ref": bulletinRef or vertex_id,
        "bulletin_type": bulletinType,
        "subject": subject or '',
        "target_audience": targetAudience or 'all',
        "effective_date": effectiveDate or now[:10],
        "status": 'distributed',
        "distributed_at": now,
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 2,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "bulletinRef": bulletinRef or vertex_id,
        "bulletinType": bulletinType,
        "bulletinStatus": "distributed",
    }


def screen_dg(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    dgClass: str = "",
    unNumber: str = "",
    quantity: float = 0.0,
    unit: str = "",
    notocRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("dg-screen")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sms_safety_report", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "dg_class": dgClass,
        "un_number": unNumber or '',
        "quantity": float(quantity),
        "unit": unit or 'kg',
        "notoc_ref": notocRef or vertex_id,
        "status": 'screened',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 2,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "flightNo": flightNo,
        "dgClass": dgClass,
        "unNumber": unNumber,
        "notocRef": notocRef or vertex_id,
        "screenStatus": "screened",
    }


def raise_security_alert(
    callerDid: str = "",
    alertRef: str = "",
    threatType: str = "",
    flightNo: str = "",
    depDate: str = "",
    threatLevel: str = "low",
    description: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("sec-alert")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sms_safety_report", {
        "vertex_id": vertex_id,
        "alert_ref": alertRef or vertex_id,
        "threat_type": threatType,
        "flight_no": flightNo or '',
        "dep_date": depDate or '',
        "threat_level": threatLevel,
        "description": description or '',
        "status": 'active',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 2,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "alertRef": alertRef or vertex_id,
        "threatType": threatType,
        "threatLevel": threatLevel,
        "alertStatus": "active",
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "air.sms.safety_report.submit": submit_safety_report,
        "air.sms.risk.assess": assess_risk,
        "air.sms.iosa.finding": record_iosa_finding,
        "air.sms.regulatory.file": file_regulatory,
        "air.sms.occurrence.report": report_occurrence,
        "air.sms.bulletin.distribute": distribute_bulletin,
        "air.sms.dg.screen": screen_dg,
        "air.sms.security.alert": raise_security_alert,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
