# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111608 — Steam Gen (segment 26).

Bespoke LangGraph implementation for Steam Generator monitoring and regulation.
This agent manages boiler state transitions, ensuring pressure and water levels
remain within safe operational parameters for steam production.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111608"
UNISPSC_TITLE = "Steam Gen"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111608"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Steam Gen
    boiler_pressure_psi: float
    water_level_percent: float
    fuel_flow_rate: float
    safety_valve_engaged: bool
    operational_status: str


def monitor_sensors(state: State) -> dict[str, Any]:
    """Reads telemetry input and updates internal boiler state metrics."""
    inp = state.get("input") or {}
    # Simulate sensor reading from input or default to nominal values
    pressure = float(inp.get("pressure", 150.0))
    water = float(inp.get("water_level", 85.0))

    status = "nominal"
    if pressure > 250.0:
        status = "high_pressure_warning"
    elif water < 30.0:
        status = "low_water_critical"

    return {
        "log": [f"{UNISPSC_CODE}:monitor_sensors -> pressure:{pressure}psi, water:{water}%"],
        "boiler_pressure_psi": pressure,
        "water_level_percent": water,
        "operational_status": status,
    }


def regulate_combustion(state: State) -> dict[str, Any]:
    """Adjusts fuel flow and safety systems based on current boiler metrics."""
    pressure = state.get("boiler_pressure_psi", 0.0)
    status = state.get("operational_status", "unknown")

    fuel_rate = 1.0
    safety_valve = False

    if pressure > 300.0:
        fuel_rate = 0.0
        safety_valve = True
        status = "emergency_shutdown"
    elif pressure > 200.0:
        fuel_rate = 0.5

    return {
        "log": [f"{UNISPSC_CODE}:regulate_combustion -> fuel_rate:{fuel_rate}, valve:{safety_valve}"],
        "fuel_flow_rate": fuel_rate,
        "safety_valve_engaged": safety_valve,
        "operational_status": status,
    }


def generate_report(state: State) -> dict[str, Any]:
    """Finalizes the state and produces the actor output payload."""
    status = state.get("operational_status", "unknown")
    is_safe = not state.get("safety_valve_engaged", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_report -> status:{status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": status,
            "safety_integrity_level": "SIL-2",
            "operational_clearance": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("monitor_sensors", monitor_sensors)
_g.add_node("regulate_combustion", regulate_combustion)
_g.add_node("generate_report", generate_report)

_g.add_edge(START, "monitor_sensors")
_g.add_edge("monitor_sensors", "regulate_combustion")
_g.add_edge("regulate_combustion", "generate_report")
_g.add_edge("generate_report", END)

graph = _g.compile()
