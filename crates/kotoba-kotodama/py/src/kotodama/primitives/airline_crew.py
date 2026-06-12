"""Airline Crew Management XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
APP_DID = "did:web:air-crew.etzhayyim.com"
ACTOR_SLUG = "air-crew"

# Flight Time Limitations (EASA/ICAO reference)
FTL_MAX_HOURS_28_DAYS = 100.0
FTL_MAX_HOURS_365_DAYS = 1000.0


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vid(kind: str, key: str) -> str:
    safe_key = key.replace("/", "_").replace(" ", "_")[:160] or uuid.uuid4().hex
    return f"air-crew:{kind}:{safe_key}"


def _new_vid(kind: str) -> str:
    return f"air-crew:{kind}:{uuid.uuid4().hex}"


def publish_roster(
    callerDid: str = "",
    rosterPeriod: str = "",
    crewCount: int = 0,
    flightCount: int = 0,
    publishedBy: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("roster", rosterPeriod)
    now = _now()
    get_kotoba_client().insert_row("vertex_air_crew_roster", {
        "vertex_id": vertex_id,
        "roster_period": rosterPeriod,
        "crew_count": int(crewCount),
        "flight_count": int(flightCount),
        "published_by": publishedBy or callerDid or APP_DID,
        "status": 'published',
        "published_at": now,
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
        "rosterPeriod": rosterPeriod,
        "crewCount": int(crewCount),
        "flightCount": int(flightCount),
        "rosterStatus": "published",
    }


def build_pairing(
    callerDid: str = "",
    pairingRef: str = "",
    crewDid: str = "",
    flightNos: str = "",
    totalFlightHours: float = 0.0,
    hours28Days: float = 0.0,
    hours365Days: float = 0.0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("pairing", pairingRef or crewDid)
    now = _now()
    ftl_compliant = (
        float(hours28Days) <= FTL_MAX_HOURS_28_DAYS
        and float(hours365Days) <= FTL_MAX_HOURS_365_DAYS
    )
    get_kotoba_client().insert_row("vertex_air_crew_roster", {
        "vertex_id": vertex_id,
        "pairing_ref": pairingRef,
        "crew_did": crewDid,
        "flight_nos": flightNos or '',
        "total_flight_hours": float(totalFlightHours),
        "hours_28_days": float(hours28Days),
        "hours_365_days": float(hours365Days),
        "ftl_compliant": ftl_compliant,
        "status": 'built',
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
        "pairingRef": pairingRef,
        "crewDid": crewDid,
        "ftlCompliant": ftl_compliant,
        "hours28Days": float(hours28Days),
        "hours365Days": float(hours365Days),
    }


def track_qualification(
    callerDid: str = "",
    crewDid: str = "",
    qualCode: str = "",
    aircraftType: str = "",
    expiryDate: str = "",
    issuingAuthority: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("qual", f"{crewDid}:{qualCode}:{aircraftType}")
    now = _now()
    today = now[:10]
    days_to_expiry = 0
    if expiryDate and expiryDate >= today:
        try:
            exp_dt = _dt.date.fromisoformat(expiryDate)
            days_to_expiry = (exp_dt - _dt.date.fromisoformat(today)).days
        except ValueError:
            days_to_expiry = 0
    get_kotoba_client().insert_row("vertex_air_crew_qualification", {
        "vertex_id": vertex_id,
        "crew_did": crewDid,
        "qual_code": qualCode,
        "aircraft_type": aircraftType,
        "expiry_date": expiryDate,
        "issuing_authority": issuingAuthority or '',
        "days_to_expiry": days_to_expiry,
        "status": 'valid' if days_to_expiry > 0 else 'expired',
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
        "crewDid": crewDid,
        "qualCode": qualCode,
        "expiryDate": expiryDate,
        "daysToExpiry": days_to_expiry,
    }


def assess_fatigue(
    callerDid: str = "",
    crewDid: str = "",
    assessmentDate: str = "",
    hoursLast24h: float = 0.0,
    hoursLast7d: float = 0.0,
    restHoursLast: float = 0.0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("fatigue")
    now = _now()
    if hoursLast24h > 12 or restHoursLast < 8:
        risk_level = "high"
    elif hoursLast24h > 9 or restHoursLast < 10:
        risk_level = "medium"
    else:
        risk_level = "low"
    get_kotoba_client().insert_row("vertex_air_crew_roster", {
        "vertex_id": vertex_id,
        "crew_did": crewDid,
        "assessment_date": assessmentDate or now[:10],
        "hours_last_24h": float(hoursLast24h),
        "hours_last_7d": float(hoursLast7d),
        "rest_hours_last": float(restHoursLast),
        "risk_level": risk_level,
        "status": 'assessed',
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
        "crewDid": crewDid,
        "riskLevel": risk_level,
        "hoursLast24h": float(hoursLast24h),
        "restHoursLast": float(restHoursLast),
    }


def assign_crew(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    crewDid: str = "",
    crewRole: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("crew-assign", f"{flightNo}:{depDate}:{crewDid}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_crew_roster", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "crew_did": crewDid,
        "crew_role": crewRole,
        "status": 'assigned',
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
        "flightNo": flightNo,
        "crewDid": crewDid,
        "crewRole": crewRole,
        "assignmentStatus": "assigned",
    }


def book_travel(
    callerDid: str = "",
    crewDid: str = "",
    deadheadFlightNo: str = "",
    depDate: str = "",
    travelType: str = "deadhead",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("travel")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_crew_roster", {
        "vertex_id": vertex_id,
        "crew_did": crewDid,
        "deadhead_flight_no": deadheadFlightNo or '',
        "dep_date": depDate,
        "travel_type": travelType,
        "status": 'booked',
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
        "crewDid": crewDid,
        "deadheadFlightNo": deadheadFlightNo,
        "travelStatus": "booked",
    }


def record_duty_time(
    callerDid: str = "",
    crewDid: str = "",
    dutyDate: str = "",
    dutyStartTime: str = "",
    dutyEndTime: str = "",
    flightHours: float = 0.0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("duty-time")
    now = _now()
    duty_hours = 0.0
    limit_breach = False
    if dutyStartTime and dutyEndTime:
        try:
            start = _dt.datetime.fromisoformat(dutyStartTime.replace("Z", "+00:00"))
            end = _dt.datetime.fromisoformat(dutyEndTime.replace("Z", "+00:00"))
            duty_hours = (end - start).total_seconds() / 3600.0
            limit_breach = duty_hours > 14.0
        except ValueError:
            duty_hours = 0.0
    get_kotoba_client().insert_row("vertex_air_crew_roster", {
        "vertex_id": vertex_id,
        "crew_did": crewDid,
        "duty_date": dutyDate or now[:10],
        "duty_start_time": dutyStartTime,
        "duty_end_time": dutyEndTime,
        "flight_hours": float(flightHours),
        "duty_hours": duty_hours,
        "limit_breach": limit_breach,
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
        "crewDid": crewDid,
        "dutyHours": duty_hours,
        "flightHours": float(flightHours),
        "limitBreach": limit_breach,
    }


def notify_crew(
    callerDid: str = "",
    crewDid: str = "",
    notificationType: str = "",
    message: str = "",
    flightNo: str = "",
    depDate: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("crew-notify")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_crew_roster", {
        "vertex_id": vertex_id,
        "crew_did": crewDid,
        "notification_type": notificationType,
        "message": message or '',
        "flight_no": flightNo or '',
        "dep_date": depDate or '',
        "status": 'sent',
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
        "crewDid": crewDid,
        "notificationType": notificationType,
        "notifyStatus": "sent",
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "air.crew.roster.publish": publish_roster,
        "air.crew.pairing.build": build_pairing,
        "air.crew.qualification.track": track_qualification,
        "air.crew.fatigue.assess": assess_fatigue,
        "air.crew.crew.assign": assign_crew,
        "air.crew.travel.book": book_travel,
        "air.crew.duty_time.record": record_duty_time,
        "air.crew.crew.notify": notify_crew,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
