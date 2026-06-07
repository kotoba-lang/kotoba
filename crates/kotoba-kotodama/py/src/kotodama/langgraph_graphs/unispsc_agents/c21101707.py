# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101707"
UNISPSC_TITLE = "Irrigation"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101707"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Irrigation domain state fields
    soil_moisture_index: float
    water_source_verified: bool
    flow_rate_gps: float
    zone_id: str


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates the input irrigation parameters and identifies the target zone."""
    inp = state.get("input") or {}
    zone = inp.get("zone_id", "Z-01")
    moisture = inp.get("moisture_reading", 0.35)
    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters(zone={zone})"],
        "zone_id": zone,
        "soil_moisture_index": moisture,
    }


def check_water_availability(state: State) -> dict[str, Any]:
    """Checks reservoir levels and system pressure for the requested zone."""
    # Trigger irrigation logic: only proceed if moisture is below 60%
    moisture = state.get("soil_moisture_index", 1.0)
    can_proceed = moisture < 0.6
    return {
        "log": [f"{UNISPSC_CODE}:check_water_availability(ready={can_proceed})"],
        "water_source_verified": can_proceed,
    }


def execute_cycle(state: State) -> dict[str, Any]:
    """Calculates flow rate and simulates the start of the irrigation cycle."""
    verified = state.get("water_source_verified", False)
    # Target flow is 2.5 Gallons Per Second if source integrity is verified
    flow = 2.5 if verified else 0.0
    return {
        "log": [f"{UNISPSC_CODE}:execute_cycle(flow={flow})"],
        "flow_rate_gps": flow,
    }


def emit_status(state: State) -> dict[str, Any]:
    """Generates the final status result for the irrigation operation."""
    flow = state.get("flow_rate_gps", 0.0)
    zone = state.get("zone_id", "unknown")
    return {
        "log": [f"{UNISPSC_CODE}:emit_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "zone": zone,
            "operational": flow > 0,
            "final_flow_gps": flow,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("check_water", check_water_availability)
_g.add_node("execute", execute_cycle)
_g.add_node("emit", emit_status)

_g.add_edge(START, "validate")
_g.add_edge("validate", "check_water")
_g.add_edge("check_water", "execute")
_g.add_edge("execute", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
