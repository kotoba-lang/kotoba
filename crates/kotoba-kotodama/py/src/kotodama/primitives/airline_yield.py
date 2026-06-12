"""Airline Yield Management XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
APP_DID = "did:web:air-yield.etzhayyim.com"
ACTOR_SLUG = "air-yield"


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vid(kind: str, key: str) -> str:
    safe_key = key.replace("/", "_").replace(" ", "_")[:160] or uuid.uuid4().hex
    return f"air-yield:{kind}:{safe_key}"


def _new_vid(kind: str) -> str:
    return f"air-yield:{kind}:{uuid.uuid4().hex}"


def publish_fare_class(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    fareClass: str = "",
    baseFare: float = 0.0,
    currency: str = "USD",
    inventory: int = 0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("fare-class", f"{flightNo}:{depDate}:{fareClass}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_yield_fare_class", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "fare_class": fareClass,
        "base_fare": float(baseFare),
        "currency": currency,
        "inventory": int(inventory),
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
        "flightNo": flightNo,
        "fareClass": fareClass,
        "baseFare": float(baseFare),
        "currency": currency,
        "inventory": int(inventory),
    }


def adjust_inventory(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    fareClass: str = "",
    delta: int = 0,
    reason: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("inv-adjust")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_yield_fare_class", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "fare_class": fareClass,
        "inventory_delta": int(delta),
        "adjust_reason": reason or '',
        "status": 'adjusted',
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
        "fareClass": fareClass,
        "delta": int(delta),
    }


def file_fare(
    callerDid: str = "",
    fareCode: str = "",
    originIata: str = "",
    destIata: str = "",
    amount: float = 0.0,
    currency: str = "USD",
    effectiveDate: str = "",
    discountCode: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("atpco-fare", f"{fareCode}:{originIata}:{destIata}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_yield_fare_class", {
        "vertex_id": vertex_id,
        "fare_code": fareCode,
        "origin_iata": originIata,
        "dest_iata": destIata,
        "amount": float(amount),
        "currency": currency,
        "effective_date": effectiveDate or now[:10],
        "discount_code": discountCode or '',
        "status": 'filed',
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
        "fareCode": fareCode,
        "originIata": originIata,
        "destIata": destIata,
        "amount": float(amount),
        "currency": currency,
    }


def set_overbooking(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    overbookingFactor: float = 1.0,
    maxOverbooking: int = 0,
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("overbooking", f"{flightNo}:{depDate}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_yield_fare_class", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "overbooking_factor": float(overbookingFactor),
        "max_overbooking": int(maxOverbooking),
        "status": 'set',
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
        "overbookingFactor": float(overbookingFactor),
        "maxOverbooking": int(maxOverbooking),
    }


def process_group(
    callerDid: str = "",
    groupRef: str = "",
    flightNo: str = "",
    depDate: str = "",
    paxCount: int = 0,
    fareClass: str = "",
    groupFare: float = 0.0,
    currency: str = "USD",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("group", groupRef or f"{flightNo}:{depDate}")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_yield_fare_class", {
        "vertex_id": vertex_id,
        "group_ref": groupRef,
        "flight_no": flightNo,
        "dep_date": depDate,
        "pax_count": int(paxCount),
        "fare_class": fareClass,
        "group_fare": float(groupFare),
        "currency": currency,
        "status": 'processed',
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
        "groupRef": groupRef,
        "flightNo": flightNo,
        "paxCount": int(paxCount),
        "groupFare": float(groupFare),
        "currency": currency,
    }


def dynamic_price(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    fareClass: str = "",
    loadFactor: float = 0.0,
    recommendedFare: float = 0.0,
    currency: str = "USD",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("dynamic-price")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_yield_fare_class", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "fare_class": fareClass,
        "load_factor": float(loadFactor),
        "recommended_fare": float(recommendedFare),
        "currency": currency,
        "status": 'priced',
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
        "fareClass": fareClass,
        "loadFactor": float(loadFactor),
        "recommendedFare": float(recommendedFare),
        "currency": currency,
    }


def revenue_report(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    paxRevenue: float = 0.0,
    cargoRevenue: float = 0.0,
    ancillaryRevenue: float = 0.0,
    currency: str = "USD",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _vid("revenue-report", f"{flightNo}:{depDate}")
    now = _now()
    total_revenue = float(paxRevenue) + float(cargoRevenue) + float(ancillaryRevenue)
    get_kotoba_client().insert_row("vertex_air_yield_fare_class", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "pax_revenue": float(paxRevenue),
        "cargo_revenue": float(cargoRevenue),
        "ancillary_revenue": float(ancillaryRevenue),
        "total_revenue": total_revenue,
        "currency": currency,
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
        "flightNo": flightNo,
        "depDate": depDate,
        "totalRevenue": total_revenue,
        "currency": currency,
    }


def demand_forecast(
    callerDid: str = "",
    flightNo: str = "",
    depDate: str = "",
    forecastPax: int = 0,
    forecastRevenue: float = 0.0,
    currency: str = "USD",
    modelVersion: str = "",
    **_: Any,
) -> dict[str, Any]:
    vertex_id = _new_vid("demand-forecast")
    now = _now()
    get_kotoba_client().insert_row("vertex_air_yield_fare_class", {
        "vertex_id": vertex_id,
        "flight_no": flightNo,
        "dep_date": depDate,
        "forecast_pax": int(forecastPax),
        "forecast_revenue": float(forecastRevenue),
        "currency": currency,
        "model_version": modelVersion or 'v1',
        "status": 'forecast',
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
        "forecastPax": int(forecastPax),
        "forecastRevenue": float(forecastRevenue),
        "currency": currency,
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "air.yield.fare_class.publish": publish_fare_class,
        "air.yield.inventory.adjust": adjust_inventory,
        "air.yield.fare.file": file_fare,
        "air.yield.overbooking.set": set_overbooking,
        "air.yield.group.process": process_group,
        "air.yield.price.dynamic": dynamic_price,
        "air.yield.revenue.report": revenue_report,
        "air.yield.demand.forecast": demand_forecast,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
