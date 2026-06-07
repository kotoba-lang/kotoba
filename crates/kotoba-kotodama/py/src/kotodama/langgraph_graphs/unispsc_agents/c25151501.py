# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25151501 — Spacecraft (segment 25).

Bespoke graph logic for spacecraft operations, telemetry validation,
and orbital trajectory calculations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25151501"
UNISPSC_TITLE = "Spacecraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25151501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Spacecraft
    telemetry_status: str
    orbital_params: dict[str, float]
    fuel_level: float
    payload_integrity: bool


def validate_telemetry(state: State) -> dict[str, Any]:
    """Validates incoming spacecraft telemetry and system health."""
    inp = state.get("input") or {}
    t_data = inp.get("telemetry", {})
    # Simple logic to determine status from input
    signal = t_data.get("signal_strength", 1.0)
    status = "nominal" if signal > 0.5 else "degraded"
    return {
        "log": [f"{UNISPSC_CODE}:validate_telemetry:{status}"],
        "telemetry_status": status,
        "fuel_level": inp.get("fuel", 100.0),
    }


def calculate_orbit(state: State) -> dict[str, Any]:
    """Computes orbital elements based on mission parameters."""
    # Simulation of Keplerian elements calculation for a LEO orbit
    params = {
        "semi_major_axis": 6771.0,
        "eccentricity": 0.0001,
        "inclination": 51.64,
    }
    return {
        "log": [f"{UNISPSC_CODE}:calculate_orbit"],
        "orbital_params": params,
        "payload_integrity": state.get("telemetry_status") == "nominal",
    }


def finalize_flight_state(state: State) -> dict[str, Any]:
    """Finalizes the spacecraft state and emits the mission update."""
    is_nominal = state.get("telemetry_status") == "nominal"
    is_ready = state.get("payload_integrity", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_flight_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mission_status": "active" if is_nominal and is_ready else "safe_mode",
            "orbital_data": state.get("orbital_params"),
            "fuel_remaining": state.get("fuel_level"),
            "ok": is_nominal and is_ready,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_telemetry", validate_telemetry)
_g.add_node("calculate_orbit", calculate_orbit)
_g.add_node("finalize_flight_state", finalize_flight_state)

_g.add_edge(START, "validate_telemetry")
_g.add_edge("validate_telemetry", "calculate_orbit")
_g.add_edge("calculate_orbit", "finalize_flight_state")
_g.add_edge("finalize_flight_state", END)

graph = _g.compile()
