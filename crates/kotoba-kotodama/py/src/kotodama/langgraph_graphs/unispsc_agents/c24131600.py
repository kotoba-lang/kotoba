# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24131600 — Freezer (segment 24).

Bespoke logic for managing freezer operations, including temperature
monitoring, setpoint validation, and thermal efficiency tracking.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24131600"
UNISPSC_TITLE = "Freezer"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24131600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Freezer monitoring
    current_temp: float
    setpoint: float
    door_open: bool
    compressor_active: bool
    efficiency_score: float


def sensor_calibration(state: State) -> dict[str, Any]:
    """Validates inputs and initializes sensor state."""
    inp = state.get("input") or {}
    # Safety clamp: Freezers typically operate between -30 and -10 Celsius
    sp = float(inp.get("setpoint", -18.0))
    sp = max(-35.0, min(-5.0, sp))

    return {
        "log": [f"{UNISPSC_CODE}:sensor_calibration"],
        "setpoint": sp,
        "current_temp": float(inp.get("current_temp", -16.5)),
        "door_open": bool(inp.get("door_open", False)),
    }


def thermal_regulation(state: State) -> dict[str, Any]:
    """Simulates the physical response of the freezer unit."""
    curr = state.get("current_temp", 0.0)
    sp = state.get("setpoint", -18.0)
    door = state.get("door_open", False)

    # Hysteresis loop logic
    compressor = curr > (sp + 1.5)
    cooling_power = -2.0 if compressor else 0.0
    ambient_leak = 1.5 if door else 0.2

    new_temp = round(curr + cooling_power + ambient_leak, 2)
    # Efficiency drops if door is open or compressor is overworked
    efficiency = 1.0
    if door:
        efficiency -= 0.5
    if compressor and curr > -5.0:
        efficiency -= 0.2

    return {
        "log": [f"{UNISPSC_CODE}:thermal_regulation"],
        "current_temp": new_temp,
        "compressor_active": compressor,
        "efficiency_score": round(efficiency, 2),
    }


def telemetry_export(state: State) -> dict[str, Any]:
    """Produces the final operational status report."""
    curr = state.get("current_temp", 0.0)
    door = state.get("door_open", False)

    status = "NOMINAL"
    if curr > -10.0:
        status = "CRITICAL_TEMP_ALARM"
    elif door:
        status = "DOOR_AJAR_WARNING"

    return {
        "log": [f"{UNISPSC_CODE}:telemetry_export"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": status,
            "metrics": {
                "temperature_celsius": curr,
                "target_celsius": state.get("setpoint"),
                "efficiency": state.get("efficiency_score"),
                "compressor_running": state.get("compressor_active")
            },
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("calibrate", sensor_calibration)
_g.add_node("regulate", thermal_regulation)
_g.add_node("export", telemetry_export)

_g.add_edge(START, "calibrate")
_g.add_edge("calibrate", "regulate")
_g.add_edge("regulate", "export")
_g.add_edge("export", END)

graph = _g.compile()
