# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111508 — Ferry.

This agent handles the lifecycle of a ferry transit, including vessel
inspection, load verification, and departure authorization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111508"
UNISPSC_TITLE = "Ferry"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific ferry state
    vessel_id: str
    passenger_count: int
    vehicle_units: int
    safety_certified: bool
    weather_clearance: bool


def inspect_vessel(state: State) -> dict[str, Any]:
    """Inspects the ferry vessel for mechanical and safety compliance."""
    inp = state.get("input") or {}
    vessel_id = inp.get("vessel_id", "V-GENERIC")
    # Simulation of safety checks
    is_certified = len(vessel_id) > 5
    return {
        "log": [f"{UNISPSC_CODE}:inspect_vessel"],
        "vessel_id": vessel_id,
        "safety_certified": is_certified,
        "weather_clearance": inp.get("visibility", 100) > 50,
    }


def validate_manifest(state: State) -> dict[str, Any]:
    """Validates the passenger and vehicle counts against vessel capacity."""
    inp = state.get("input") or {}
    p_count = inp.get("passengers", 0)
    v_units = inp.get("vehicles", 0)

    # Logic: Maximum 500 equivalent units; vehicles count as 5 units
    total_load = p_count + (v_units * 5)
    valid_load = total_load <= 500

    return {
        "log": [f"{UNISPSC_CODE}:validate_manifest"],
        "passenger_count": p_count,
        "vehicle_units": v_units,
        "load_valid": valid_load,
    }


def authorize_transit(state: State) -> dict[str, Any]:
    """Finalizes departure authorization based on safety and manifest checks."""
    safe = state.get("safety_certified", False)
    weather = state.get("weather_clearance", False)
    valid_load = state.get("load_valid", False)

    authorized = safe and weather and valid_load

    return {
        "log": [f"{UNISPSC_CODE}:authorize_transit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "AUTHORIZED" if authorized else "HOLD",
            "vessel": state.get("vessel_id"),
            "load_summary": {
                "p": state.get("passenger_count"),
                "v": state.get("vehicle_units")
            },
            "ok": authorized,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_vessel)
_g.add_node("validate", validate_manifest)
_g.add_node("authorize", authorize_transit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "validate")
_g.add_edge("validate", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
