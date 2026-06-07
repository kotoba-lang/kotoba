"""Airline Cargo XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
APP_DID = "did:web:air-cargo.etzhayyim.com"
ACTOR_SLUG = "air-cargo"


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vid(kind: str, key: str) -> str:
    safe_key = key.replace("/", "_").replace(" ", "_")[:160] or uuid.uuid4().hex
    return f"air-cargo:{kind}:{safe_key}"


def _new_vid(kind: str) -> str:
    return f"air-cargo:{kind}:{uuid.uuid4().hex}"


def create_cargo_booking(
    callerDid: str = "",
    bookingRef: str = "",
    originIata: str = "",
    destIata: str = "",
    flightNo: str = "",
    depDate: str = "",
    weightKg: float = 0.0,
    commodity: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("booking", bookingRef or f"{flightNo}:{depDate}:{originIata}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_cargo_booking", {
        "vertex_id": vertex_id,
        "booking_ref": bookingRef or vertex_id,
        "origin_iata": originIata,
        "dest_iata": destIata,
        "flight_no": flightNo,
        "dep_date": depDate,
        "weight_kg": float(weightKg),
        "commodity": commodity or '',
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
        "bookingRef": bookingRef or vertex_id,
        "flightNo": flightNo,
        "weightKg": float(weightKg),
        "bookingStatus": "booked",
    }


def issue_awb(
    callerDid: str = "",
    awbNumber: str = "",
    bookingRef: str = "",
    shipperName: str = "",
    consigneeName: str = "",
    originIata: str = "",
    destIata: str = "",
    chargeableWeightKg: float = 0.0,
    currency: str = "USD",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("awb", awbNumber or bookingRef)
    now = _now()
    get_kotoba_client().insert_row("vertex_air_cargo_awb", {
        "vertex_id": vertex_id,
        "awb_number": awbNumber,
        "booking_ref": bookingRef,
        "shipper_name": shipperName or '',
        "consignee_name": consigneeName or '',
        "origin_iata": originIata,
        "dest_iata": destIata,
        "chargeable_weight_kg": float(chargeableWeightKg),
        "currency": currency,
        "status": 'issued',
        "issued_at": now,
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
        "awbNumber": awbNumber,
        "bookingRef": bookingRef,
        "chargeableWeightKg": float(chargeableWeightKg),
        "awbStatus": "issued",
    }


def accept_cargo(
    callerDid: str = "",
    awbNumber: str = "",
    flightNo: str = "",
    depDate: str = "",
    actualWeightKg: float = 0.0,
    pieces: int = 1,
    specialHandling: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("cargo-accept")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_cargo_booking", {
        "vertex_id": vertex_id,
        "awb_number": awbNumber,
        "flight_no": flightNo,
        "dep_date": depDate,
        "actual_weight_kg": float(actualWeightKg),
        "pieces": int(pieces),
        "special_handling": specialHandling or '',
        "status": 'accepted',
        "accepted_at": now,
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
        "awbNumber": awbNumber,
        "actualWeightKg": float(actualWeightKg),
        "pieces": int(pieces),
        "acceptanceStatus": "accepted",
    }


def assign_uld(
    callerDid: str = "",
    uldNumber: str = "",
    flightNo: str = "",
    depDate: str = "",
    awbNumbers: str = "",
    loadedWeightKg: float = 0.0,
    position: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("uld", f"{uldNumber}:{flightNo}:{depDate}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_cargo_booking", {
        "vertex_id": vertex_id,
        "uld_number": uldNumber,
        "flight_no": flightNo,
        "dep_date": depDate,
        "awb_numbers": awbNumbers or '',
        "loaded_weight_kg": float(loadedWeightKg),
        "position": position or '',
        "status": 'loaded',
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
        "uldNumber": uldNumber,
        "flightNo": flightNo,
        "loadedWeightKg": float(loadedWeightKg),
        "uldStatus": "loaded",
    }


def track_shipment(
    callerDid: str = "",
    awbNumber: str = "",
    eventType: str = "",
    eventStation: str = "",
    eventTime: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("track")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_cargo_booking", {
        "vertex_id": vertex_id,
        "awb_number": awbNumber,
        "event_type": eventType,
        "event_station": eventStation or '',
        "event_time": eventTime or now,
        "status": eventType.lower().replace(' ', '_') or 'tracked',
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
        "awbNumber": awbNumber,
        "eventType": eventType,
        "eventStation": eventStation,
        "eventTime": eventTime or now,
    }


def process_claim(
    callerDid: str = "",
    claimRef: str = "",
    awbNumber: str = "",
    claimType: str = "",
    claimAmount: float = 0.0,
    currency: str = "USD",
    description: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("claim", claimRef or awbNumber)
    now = _now()
    get_kotoba_client().insert_row("vertex_air_cargo_booking", {
        "vertex_id": vertex_id,
        "claim_ref": claimRef or vertex_id,
        "awb_number": awbNumber,
        "claim_type": claimType,
        "claim_amount": float(claimAmount),
        "currency": currency,
        "description": description or '',
        "status": 'under_review',
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
        "claimRef": claimRef or vertex_id,
        "awbNumber": awbNumber,
        "claimAmount": float(claimAmount),
        "claimStatus": "under_review",
    }


def settle_cass(
    callerDid: str = "",
    agentCode: str = "",
    settlementPeriod: str = "",
    awbCount: int = 0,
    grossAmount: float = 0.0,
    netAmount: float = 0.0,
    currency: str = "USD",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("cass-settlement", f"{agentCode}:{settlementPeriod}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_cargo_cass_settlement", {
        "vertex_id": vertex_id,
        "agent_code": agentCode,
        "settlement_period": settlementPeriod,
        "awb_count": int(awbCount),
        "gross_amount": float(grossAmount),
        "net_amount": float(netAmount),
        "currency": currency,
        "status": 'settled',
        "settled_at": now,
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
        "agentCode": agentCode,
        "settlementPeriod": settlementPeriod,
        "netAmount": float(netAmount),
        "currency": currency,
        "settlementStatus": "settled",
    }


def report_cargo_security(
    callerDid: str = "",
    screeningRef: str = "",
    flightNo: str = "",
    depDate: str = "",
    method: str = "",
    awbNumber: str = "",
    result: str = "clear",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("cargo-sec")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_cargo_booking", {
        "vertex_id": vertex_id,
        "screening_ref": screeningRef or vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "method": method or 'x-ray',
        "awb_number": awbNumber or '',
        "result": result,
        "status": 'screened',
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
        "screeningRef": screeningRef or vertex_id,
        "flightNo": flightNo,
        "awbNumber": awbNumber,
        "result": result,
        "securityStatus": "screened",
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "air.cargo.booking.create": create_cargo_booking,
        "air.cargo.awb.issue": issue_awb,
        "air.cargo.cargo.accept": accept_cargo,
        "air.cargo.uld.assign": assign_uld,
        "air.cargo.shipment.track": track_shipment,
        "air.cargo.claim.process": process_claim,
        "air.cargo.cass.settle": settle_cass,
        "air.cargo.security.report": report_cargo_security,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
