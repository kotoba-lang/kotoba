"""Airline Scheduling XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import hashlib
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
APP_DID = "did:web:air-sched.etzhayyim.com"
ACTOR_SLUG = "air-sched"


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vid(kind: str, key: str) -> str:
    safe_key = key.replace("/", "_").replace(" ", "_")[:160] or uuid.uuid4().hex
    return f"air-sched:{kind}:{safe_key}"


def _new_vid(kind: str) -> str:
    return f"air-sched:{kind}:{uuid.uuid4().hex}"


def register_schedule(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    depIata: str = "",
    arrIata: str = "",
    depTime: str = "",
    arrTime: str = "",
    aircraftType: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("schedule", f"{flightNo}:{depDate}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sched_schedule", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "dep_iata": depIata,
        "arr_iata": arrIata,
        "dep_time": depTime,
        "arr_time": arrTime,
        "aircraft_type": aircraftType or '',
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
        "flightNo": flightNo,
        "depDate": depDate,
        "depIata": depIata,
        "arrIata": arrIata,
    }


def request_slot(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    depIata: str = "",
    slotType: str = "departure",
    requestedTime: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("slot", f"{flightNo}:{depDate}:{slotType}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sched_slot", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "dep_iata": depIata,
        "slot_type": slotType,
        "requested_time": requestedTime,
        "status": 'requested',
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
        "slotType": slotType,
        "requestedTime": requestedTime,
    }


def allocate_slot(
    callerDid: str = "",
    slotRef: str = "",
    allocatedTime: str = "",
    allocatedBy: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("slot-alloc")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sched_slot", {
        "vertex_id": vertex_id,
        "slot_ref": slotRef,
        "allocated_time": allocatedTime,
        "allocated_by": allocatedBy or '',
        "status": 'allocated',
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
        "slotRef": slotRef,
        "allocatedTime": allocatedTime,
        "slotStatus": "allocated",
    }


def assign_fleet(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    aircraftType: str = "",
    tailNumber: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("fleet-assign")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sched_schedule", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "aircraft_type": aircraftType,
        "tail_number": tailNumber or '',
        "status": 'fleet_assigned',
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
        "depDate": depDate,
        "aircraftType": aircraftType,
        "tailNumber": tailNumber,
    }


def publish_schedule(
    callerDid: str = "",
    seasonCode: str = "",
    validFrom: str = "",
    validTo: str = "",
    flightCount: int = 0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("schedule-pub", seasonCode)
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sched_schedule", {
        "vertex_id": vertex_id,
        "season_code": seasonCode,
        "valid_from": validFrom,
        "valid_to": validTo,
        "flight_count": int(flightCount),
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
        "seasonCode": seasonCode,
        "publishedAt": now,
        "flightCount": int(flightCount),
    }


def assign_gate(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    gateCode: str = "",
    terminal: str = "",
    airport: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("gate", f"{flightNo}:{depDate}:{airport}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sched_schedule", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "gate_code": gateCode,
        "terminal": terminal or '',
        "airport": airport or '',
        "status": 'gate_assigned',
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
        "gateCode": gateCode,
        "terminal": terminal,
    }


def change_frequency(
    callerDid: str = "",
    flightNo: str = "",
    seasonCode: str = "",
    oldFrequency: str = "",
    newFrequency: str = "",
    effectiveDate: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("freq-change")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sched_schedule", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "season_code": seasonCode,
        "old_frequency": oldFrequency,
        "new_frequency": newFrequency,
        "effective_date": effectiveDate or now[:10],
        "status": 'frequency_changed',
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
        "oldFrequency": oldFrequency,
        "newFrequency": newFrequency,
        "effectiveDate": effectiveDate,
    }


def register_codeshare(
    callerDid: str = "",
    operatingFlightNo: str = "",
    marketingFlightNo: str = "",
    partnerAirline: str = "",
    depDate: str = "",
    seatAllocation: int = 0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("codeshare", f"{operatingFlightNo}:{marketingFlightNo}:{depDate}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_sched_codeshare", {
        "vertex_id": vertex_id,
        "operating_flight_no": operatingFlightNo,
        "marketing_flight_no": marketingFlightNo,
        "partner_airline": partnerAirline,
        "dep_date": depDate,
        "seat_allocation": int(seatAllocation),
        "status": 'active',
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
        "operatingFlightNo": operatingFlightNo,
        "marketingFlightNo": marketingFlightNo,
        "partnerAirline": partnerAirline,
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "air.sched.schedule.register": register_schedule,
        "air.sched.slot.request": request_slot,
        "air.sched.slot.allocate": allocate_slot,
        "air.sched.fleet.assign": assign_fleet,
        "air.sched.schedule.publish": publish_schedule,
        "air.sched.gate.assign": assign_gate,
        "air.sched.frequency.change": change_frequency,
        "air.sched.codeshare.register": register_codeshare,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
