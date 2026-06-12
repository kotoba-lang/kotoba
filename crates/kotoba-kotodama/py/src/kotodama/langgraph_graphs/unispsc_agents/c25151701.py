# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25151701 — Satellite (segment 25).

Bespoke graph logic for satellite telemetry and orbital validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25151701"
UNISPSC_TITLE = "Satellite"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25151701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Satellite
    orbit_type: str
    telemetry_active: bool
    link_budget_db: float
    payload_health: str


def check_orbital_insertion(state: State) -> dict[str, Any]:
    """Validates the orbital parameters from input."""
    inp = state.get("input") or {}
    altitude = inp.get("altitude_km", 0)

    if altitude < 2000:
        o_type = "LEO"
    elif altitude < 35000:
        o_type = "MEO"
    else:
        o_type = "GEO"

    return {
        "log": [f"{UNISPSC_CODE}:check_orbital_insertion:{o_type}"],
        "orbit_type": o_type,
        "telemetry_active": altitude > 0
    }


def calibrate_transponders(state: State) -> dict[str, Any]:
    """Calculates link budget and verifies payload status."""
    is_active = state.get("telemetry_active", False)
    budget = 45.5 if is_active else 0.0
    status = "nominal" if budget > 40 else "degraded"

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_transponders:{status}"],
        "link_budget_db": budget,
        "payload_health": status
    }


def finalize_mission_data(state: State) -> dict[str, Any]:
    """Emits the final satellite state and metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_mission_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "orbit": state.get("orbit_type"),
                "link_db": state.get("link_budget_db"),
                "health": state.get("payload_health"),
            },
            "status": "ready_for_uplink" if state.get("telemetry_active") else "idle"
        },
    }


_g = StateGraph(State)
_g.add_node("check_orbital_insertion", check_orbital_insertion)
_g.add_node("calibrate_transponders", calibrate_transponders)
_g.add_node("finalize_mission_data", finalize_mission_data)

_g.add_edge(START, "check_orbital_insertion")
_g.add_edge("check_orbital_insertion", "calibrate_transponders")
_g.add_edge("calibrate_transponders", "finalize_mission_data")
_g.add_edge("finalize_mission_data", END)

graph = _g.compile()
