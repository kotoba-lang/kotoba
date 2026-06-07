"""Airline MRO (Maintenance, Repair & Overhaul) XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
APP_DID = "did:web:air-mro.etzhayyim.com"
ACTOR_SLUG = "air-mro"


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vid(kind: str, key: str) -> str:
    safe_key = key.replace("/", "_").replace(" ", "_")[:160] or uuid.uuid4().hex
    return f"air-mro:{kind}:{safe_key}"


def _new_vid(kind: str) -> str:
    return f"air-mro:{kind}:{uuid.uuid4().hex}"


def create_work_order(
    callerDid: str = "",
    tailNumber: str = "",
    workOrderRef: str = "",
    taskType: str = "",
    description: str = "",
    priority: str = "routine",
    dueDate: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("work-order", workOrderRef or f"{tailNumber}:{taskType}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_mro_work_order", {
        "vertex_id": vertex_id,
        "tail_number": tailNumber,
        "work_order_ref": workOrderRef or vertex_id,
        "task_type": taskType,
        "description": description or '',
        "priority": priority,
        "due_date": dueDate or now[:10],
        "status": 'open',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 1,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "workOrderRef": workOrderRef or vertex_id,
        "tailNumber": tailNumber,
        "priority": priority,
        "workOrderStatus": "open",
    }


def track_component(
    callerDid: str = "",
    partNumber: str = "",
    serialNumber: str = "",
    tailNumber: str = "",
    installDate: str = "",
    cyclesSinceNew: int = 0,
    hoursSinceNew: float = 0.0,
    nextDueDate: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("component", f"{partNumber}:{serialNumber}")
    now = _now()
    today = now[:10]
    days_to_next_due = 0
    if nextDueDate and nextDueDate >= today:
        try:
            due_dt = _dt.date.fromisoformat(nextDueDate)
            days_to_next_due = (due_dt - _dt.date.fromisoformat(today)).days
        except ValueError:
            days_to_next_due = 0
    get_kotoba_client().insert_row("vertex_air_mro_component", {
        "vertex_id": vertex_id,
        "part_number": partNumber,
        "serial_number": serialNumber,
        "tail_number": tailNumber,
        "install_date": installDate or today,
        "cycles_since_new": int(cyclesSinceNew),
        "hours_since_new": float(hoursSinceNew),
        "next_due_date": nextDueDate,
        "days_to_next_due": days_to_next_due,
        "status": 'serviceable',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 1,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "partNumber": partNumber,
        "serialNumber": serialNumber,
        "daysToNextDue": days_to_next_due,
        "componentStatus": "serviceable",
    }


def check_airworthiness(
    callerDid: str = "",
    tailNumber: str = "",
    checkType: str = "",
    checkDate: str = "",
    expiryDate: str = "",
    inspector: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("airworthiness", f"{tailNumber}:{checkType}")
    now = _now()
    today = now[:10]
    days_until_due = 0
    if expiryDate and expiryDate >= today:
        try:
            exp_dt = _dt.date.fromisoformat(expiryDate)
            days_until_due = (exp_dt - _dt.date.fromisoformat(today)).days
        except ValueError:
            days_until_due = 0
    get_kotoba_client().insert_row("vertex_air_mro_work_order", {
        "vertex_id": vertex_id,
        "tail_number": tailNumber,
        "check_type": checkType,
        "check_date": checkDate or today,
        "expiry_date": expiryDate,
        "inspector": inspector or '',
        "days_until_due": days_until_due,
        "status": 'airworthy',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 1,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "tailNumber": tailNumber,
        "checkType": checkType,
        "expiryDate": expiryDate,
        "daysUntilDue": days_until_due,
        "airworthinessStatus": "airworthy",
    }


def report_occurrence(
    callerDid: str = "",
    tailNumber: str = "",
    flightNo: str = "",
    occurrenceDate: str = "",
    category: str = "",
    description: str = "",
    reportRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("occurrence")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_mro_work_order", {
        "vertex_id": vertex_id,
        "tail_number": tailNumber,
        "flight_no": flightNo or '',
        "occurrence_date": occurrenceDate or now[:10],
        "category": category or '',
        "description": description or '',
        "report_ref": reportRef or vertex_id,
        "status": 'reported',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 1,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "tailNumber": tailNumber,
        "occurrenceDate": occurrenceDate or now[:10],
        "reportRef": reportRef or vertex_id,
        "occurrenceStatus": "reported",
    }


def schedule_maintenance(
    callerDid: str = "",
    tailNumber: str = "",
    checkType: str = "",
    scheduledDate: str = "",
    estimatedDays: int = 1,
    hangarCode: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("maint-sched", f"{tailNumber}:{checkType}:{scheduledDate}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_mro_work_order", {
        "vertex_id": vertex_id,
        "tail_number": tailNumber,
        "check_type": checkType,
        "scheduled_date": scheduledDate or now[:10],
        "estimated_days": int(estimatedDays),
        "hangar_code": hangarCode or '',
        "status": 'scheduled',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 1,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "tailNumber": tailNumber,
        "checkType": checkType,
        "scheduledDate": scheduledDate or now[:10],
        "maintenanceStatus": "scheduled",
    }


def reliability_report(
    callerDid: str = "",
    tailNumber: str = "",
    reportPeriod: str = "",
    dispatchReliability: float = 0.0,
    technicalDelayCount: int = 0,
    pireps: int = 0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("reliability", f"{tailNumber}:{reportPeriod}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_mro_work_order", {
        "vertex_id": vertex_id,
        "tail_number": tailNumber,
        "report_period": reportPeriod,
        "dispatch_reliability": float(dispatchReliability),
        "technical_delay_count": int(technicalDelayCount),
        "pireps": int(pireps),
        "status": 'reported',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 1,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "tailNumber": tailNumber,
        "reportPeriod": reportPeriod,
        "dispatchReliability": float(dispatchReliability),
    }


def order_spare_part(
    callerDid: str = "",
    partNumber: str = "",
    quantity: int = 1,
    supplierCode: str = "",
    urgency: str = "routine",
    workOrderRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("spare-order")
    now = _now()
    aog_escalated = urgency.lower() == "aog"
    get_kotoba_client().insert_row("vertex_air_mro_component", {
        "vertex_id": vertex_id,
        "part_number": partNumber,
        "quantity": int(quantity),
        "supplier_code": supplierCode or '',
        "urgency": urgency,
        "work_order_ref": workOrderRef or '',
        "aog_escalated": aog_escalated,
        "status": 'ordered',
        "ordered_at": now,
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 1,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "partNumber": partNumber,
        "quantity": int(quantity),
        "urgency": urgency,
        "aogEscalated": aog_escalated,
        "orderStatus": "ordered",
    }


def record_gse(
    callerDid: str = "",
    gseId: str = "",
    gseType: str = "",
    iataCode: str = "",
    serviceDate: str = "",
    nextServiceDate: str = "",
    operationalStatus: str = "serviceable",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("gse", f"{gseId}:{iataCode}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_mro_work_order", {
        "vertex_id": vertex_id,
        "gse_id": gseId,
        "gse_type": gseType,
        "iata_code": iataCode,
        "service_date": serviceDate or now[:10],
        "next_service_date": nextServiceDate or '',
        "operational_status": operationalStatus,
        "status": 'recorded',
        "created_at": now,
        "actor_did": APP_DID,
        "org_id": 'anon',
        "user_id": callerDid or APP_DID,
        "actor_id": ACTOR_SLUG,
        "sensitivity_ord": 1,
        "owner_did": callerDid or APP_DID,
    })
    return {
        "vertexId": vertex_id,
        "status": "ok",
        "gseId": gseId,
        "gseType": gseType,
        "iataCode": iataCode,
        "operationalStatus": operationalStatus,
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "air.mro.work_order.create": create_work_order,
        "air.mro.component.track": track_component,
        "air.mro.airworthiness.check": check_airworthiness,
        "air.mro.occurrence.report": report_occurrence,
        "air.mro.maintenance.schedule": schedule_maintenance,
        "air.mro.reliability.report": reliability_report,
        "air.mro.spare_part.order": order_spare_part,
        "air.mro.gse.record": record_gse,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
