# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131601 — Helicopter (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131601"
UNISPSC_TITLE = "Helicopter"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Helicopter
    airworthiness_certified: bool
    fuel_load_liters: float
    manifest_weight_kg: float
    rotor_clearance_verified: bool
    flight_plan_filed: bool


def inspect_airframe(state: State) -> dict[str, Any]:
    """Performs structural and mechanical inspection of the helicopter."""
    inp = state.get("input") or {}
    certified = inp.get("maintenance_record", "valid") == "valid"
    rotor_check = inp.get("rotor_inspection", True)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_airframe"],
        "airworthiness_certified": certified,
        "rotor_clearance_verified": rotor_check,
    }


def calculate_weight_balance(state: State) -> dict[str, Any]:
    """Calculates weight and balance based on fuel levels and cargo manifest."""
    inp = state.get("input") or {}
    fuel = inp.get("fuel_request", 800.0)
    cargo = inp.get("cargo_weight", 250.0)

    # Helicopters have strict weight limits; assuming a 2500kg threshold for this model
    is_safe_load = (fuel * 0.8 + cargo) < 2500.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_weight_balance"],
        "fuel_load_liters": fuel,
        "manifest_weight_kg": cargo,
        "flight_plan_filed": is_safe_load,
    }


def authorize_takeoff(state: State) -> dict[str, Any]:
    """Final check of all systems and certification for flight operations."""
    ready = all([
        state.get("airworthiness_certified", False),
        state.get("rotor_clearance_verified", False),
        state.get("flight_plan_filed", False)
    ])

    return {
        "log": [f"{UNISPSC_CODE}:authorize_takeoff"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "takeoff_authorized": ready,
            "mission_status": "READY" if ready else "HOLD",
            "telemetry_summary": {
                "fuel_liters": state.get("fuel_load_liters"),
                "cargo_kg": state.get("manifest_weight_kg")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_airframe", inspect_airframe)
_g.add_node("calculate_weight_balance", calculate_weight_balance)
_g.add_node("authorize_takeoff", authorize_takeoff)

_g.add_edge(START, "inspect_airframe")
_g.add_edge("inspect_airframe", "calculate_weight_balance")
_g.add_edge("calculate_weight_balance", "authorize_takeoff")
_g.add_edge("authorize_takeoff", END)

graph = _g.compile()
