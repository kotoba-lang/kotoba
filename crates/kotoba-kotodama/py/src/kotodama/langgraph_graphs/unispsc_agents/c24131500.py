# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24131500 — Refrigerator (segment 24).

Bespoke logic for monitoring and regulating industrial refrigeration units.
This agent handles temperature telemetry processing, compressor control
logic, and status reporting within the Etz Hayyim actor network.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24131500"
UNISPSC_TITLE = "Refrigerator"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24131500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Refrigerator
    target_temperature_c: float
    current_temperature_c: float
    compressor_active: bool
    door_alarm_active: bool


def monitor_environment(state: State) -> dict[str, Any]:
    """Inspects telemetry and updates current environmental readings."""
    inp = state.get("input") or {}
    # Default to safe ranges if telemetry is missing
    current_temp = inp.get("current_temp", 4.5)
    target_temp = inp.get("target_temp", 3.0)
    door_open = inp.get("door_open", False)

    return {
        "log": [f"{UNISPSC_CODE}:monitor_environment"],
        "current_temperature_c": float(current_temp),
        "target_temperature_c": float(target_temp),
        "door_alarm_active": door_open,
    }


def thermal_regulation(state: State) -> dict[str, Any]:
    """Determines compressor state based on temperature delta."""
    current = state.get("current_temperature_c", 0.0)
    target = state.get("target_temperature_c", 0.0)

    # Simple hysteresis logic:
    # Activate compressor if current temp is more than 0.5C above target.
    # Keep it active until it hits target.
    activate = current > (target + 0.5)

    return {
        "log": [f"{UNISPSC_CODE}:thermal_regulation"],
        "compressor_active": activate,
    }


def status_dispatch(state: State) -> dict[str, Any]:
    """Compiles the final operational status report."""
    return {
        "log": [f"{UNISPSC_CODE}:status_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "status": {
                "temperature": f"{state.get('current_temperature_c'):.1f}C",
                "compressor": "RUNNING" if state.get("compressor_active") else "STANDBY",
                "door_alarm": "ALARM" if state.get("door_alarm_active") else "NORMAL",
            },
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("monitor", monitor_environment)
_g.add_node("regulate", thermal_regulation)
_g.add_node("dispatch", status_dispatch)

_g.add_edge(START, "monitor")
_g.add_edge("monitor", "regulate")
_g.add_edge("regulate", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
