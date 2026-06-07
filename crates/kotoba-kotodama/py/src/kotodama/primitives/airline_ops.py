"""Airline Operations Control XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
APP_DID = "did:web:air-ops.etzhayyim.com"
ACTOR_SLUG = "air-ops"


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vid(kind: str, key: str) -> str:
    safe_key = key.replace("/", "_").replace(" ", "_")[:160] or uuid.uuid4().hex
    return f"air-ops:{kind}:{safe_key}"


def _new_vid(kind: str) -> str:
    return f"air-ops:{kind}:{uuid.uuid4().hex}"


def file_flight_plan(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    depIata: str = "",
    arrIata: str = "",
    route: str = "",
    altIata: str = "",
    fuelOnBoard: float = 0.0,
    estimatedFlightTime: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("flight-plan", f"{flightNo}:{depDate}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ops_flight_plan", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "dep_iata": depIata,
        "arr_iata": arrIata,
        "route": route or '',
        "alt_iata": altIata or '',
        "fuel_on_board": float(fuelOnBoard),
        "estimated_flight_time": estimatedFlightTime or '',
        "status": 'filed',
        "filed_at": now,
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
        "flightPlanStatus": "filed",
    }


def dispatch_brief(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    captainDid: str = "",
    weatherSummary: str = "",
    notamCount: int = 0,
    releaseRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("dispatch-brief", f"{flightNo}:{depDate}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ops_flight_plan", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "captain_did": captainDid or '',
        "weather_summary": weatherSummary or '',
        "notam_count": int(notamCount),
        "release_ref": releaseRef or vertex_id,
        "status": 'briefed',
        "briefed_at": now,
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
        "releaseRef": releaseRef or vertex_id,
        "briefStatus": "briefed",
    }


def fetch_notam(
    callerDid: str = "",
    iataCode: str = "",
    notamType: str = "all",
    validFrom: str = "",
    validTo: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("notam-fetch")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ops_flight_plan", {
        "vertex_id": vertex_id,
        "iata_code": iataCode,
        "notam_type": notamType,
        "valid_from": validFrom or now[:10],
        "valid_to": validTo or now[:10],
        "status": 'fetched',
        "fetched_at": now,
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
        "iataCode": iataCode,
        "notamType": notamType,
        "fetchStatus": "fetched",
        "notamCount": 0,
    }


def fetch_weather(
    callerDid: str = "",
    iataCode: str = "",
    reportType: str = "metar",
    validTime: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("weather-fetch")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ops_flight_plan", {
        "vertex_id": vertex_id,
        "iata_code": iataCode,
        "report_type": reportType,
        "valid_time": validTime or now,
        "status": 'fetched',
        "fetched_at": now,
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
        "iataCode": iataCode,
        "reportType": reportType,
        "fetchStatus": "fetched",
    }


def record_tech_log(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    tailNumber: str = "",
    defectCode: str = "",
    description: str = "",
    rectification: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("tech-log")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ops_tech_log", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "tail_number": tailNumber,
        "defect_code": defectCode or '',
        "description": description or '',
        "rectification": rectification or '',
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
        "flightNo": flightNo,
        "tailNumber": tailNumber,
        "defectCode": defectCode,
        "techLogStatus": "recorded",
    }


def order_fuel(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    depIata: str = "",
    fuelType: str = "JET-A",
    requestedKg: float = 0.0,
    upliftRef: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("fuel-order", f"{flightNo}:{depDate}:{depIata}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ops_flight_plan", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "dep_iata": depIata,
        "fuel_type": fuelType,
        "requested_kg": float(requestedKg),
        "uplift_ref": upliftRef or vertex_id,
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
        "flightNo": flightNo,
        "fuelType": fuelType,
        "requestedKg": float(requestedKg),
        "upliftRef": upliftRef or vertex_id,
    }


def submit_pirep(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    reportTime: str = "",
    altitude: int = 0,
    turbulenceLevel: str = "",
    icingLevel: str = "",
    windSpeed: int = 0,
    windDir: int = 0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("pirep")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_ops_flight_plan", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "report_time": reportTime or now,
        "altitude": int(altitude),
        "turbulence_level": turbulenceLevel or 'nil',
        "icing_level": icingLevel or 'nil',
        "wind_speed": int(windSpeed),
        "wind_dir": int(windDir),
        "status": 'submitted',
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
        "turbulenceLevel": turbulenceLevel or "nil",
        "pirepStatus": "submitted",
    }


def monitor_flight(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    phase: str = "",
    delayMins: int = 0,
    positionLat: float = 0.0,
    positionLon: float = 0.0,
    altitudeFt: int = 0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("monitor")
    now = _now()
    if delayMins <= 15:
        alert_level = "green"
    elif delayMins <= 60:
        alert_level = "amber"
    else:
        alert_level = "red"
    get_kotoba_client().insert_row("vertex_air_ops_flight_plan", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "phase": phase or 'en_route',
        "delay_mins": int(delayMins),
        "position_lat": float(positionLat),
        "position_lon": float(positionLon),
        "altitude_ft": int(altitudeFt),
        "alert_level": alert_level,
        "status": 'monitored',
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
        "phase": phase or "en_route",
        "delayMins": int(delayMins),
        "alertLevel": alert_level,
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "air.ops.flight_plan.file": file_flight_plan,
        "air.ops.dispatch.brief": dispatch_brief,
        "air.ops.notam.fetch": fetch_notam,
        "air.ops.weather.fetch": fetch_weather,
        "air.ops.tech_log.record": record_tech_log,
        "air.ops.fuel.order": order_fuel,
        "air.ops.pirep.submit": submit_pirep,
        "air.ops.flight.monitor": monitor_flight,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
