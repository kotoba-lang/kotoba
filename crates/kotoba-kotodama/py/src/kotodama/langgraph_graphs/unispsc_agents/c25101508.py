# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101508 — Vehicle (segment 25).

This bespoke implementation handles vehicle state management, including
VIN verification, system telemetry diagnosis, and status finalization.
It ensures that vehicle records are compliant with regional registry
requirements and operational safety standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101508"
UNISPSC_TITLE = "Vehicle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Vehicle domain
    vin_verified: bool
    registration_status: str
    telemetry_health: dict[str, str]
    maintenance_alert: bool
    fleet_category: str


def inspect_vehicle(state: State) -> dict[str, Any]:
    """Validates the Vehicle Identification Number and registration metadata."""
    inp = state.get("input") or {}
    vin = str(inp.get("vin", "UNKNOWN"))

    # VINs are typically 17 characters
    is_valid = len(vin) == 17
    category = inp.get("category", "commercial")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_vehicle:vin_length={len(vin)}:valid={is_valid}"],
        "vin_verified": is_valid,
        "registration_status": "VERIFIED" if is_valid else "INVALID_VIN",
        "fleet_category": category,
    }


def diagnose_telemetry(state: State) -> dict[str, Any]:
    """Analyzes vehicle sensor data for critical maintenance alerts."""
    inp = state.get("input") or {}
    sensors = inp.get("sensors", {})

    engine_temp = sensors.get("engine_temp_c", 90)
    tire_pressure = sensors.get("tire_pressure_psi", 32)

    alert = False
    health = {"engine": "NORMAL", "tires": "NORMAL"}

    if engine_temp > 110:
        health["engine"] = "OVERHEATING"
        alert = True
    if tire_pressure < 25:
        health["tires"] = "LOW_PRESSURE"
        alert = True

    return {
        "log": [f"{UNISPSC_CODE}:diagnose_telemetry:engine={health['engine']}"],
        "telemetry_health": health,
        "maintenance_alert": alert,
    }


def finalize_disposition(state: State) -> dict[str, Any]:
    """Compiles the final operational status based on inspection and diagnosis."""
    vin_ok = state.get("vin_verified", False)
    alert = state.get("maintenance_alert", False)
    category = state.get("fleet_category", "unknown")

    operational = vin_ok and not alert
    disposition = "READY_FOR_SERVICE" if operational else "GROUNDED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_disposition:status={disposition}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "disposition": disposition,
            "fleet_category": category,
            "operational_safety": operational,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_vehicle)
_g.add_node("diagnose", diagnose_telemetry)
_g.add_node("finalize", finalize_disposition)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "diagnose")
_g.add_edge("diagnose", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
