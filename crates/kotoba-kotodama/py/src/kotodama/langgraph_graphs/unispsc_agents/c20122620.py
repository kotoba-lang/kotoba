# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122620 — Actuator.
Bespoke logic for controlling and monitoring mechanical actuators in industrial settings.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122620"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122620"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Actuator (Well completion equipment)
    target_position_pct: float
    current_position_pct: float
    hydraulic_pressure_psi: float
    valve_status: str
    cycle_count: int


def calibrate_actuator(state: State) -> dict[str, Any]:
    """Initial calibration and setup of the actuator control state."""
    inp = state.get("input") or {}
    target = float(inp.get("target", 100.0))
    pressure = float(inp.get("pressure", 1500.0))

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_actuator - Initializing to {target}%"],
        "target_position_pct": target,
        "current_position_pct": 0.0,
        "hydraulic_pressure_psi": pressure,
        "valve_status": "closed",
        "cycle_count": int(inp.get("cycles", 0)) + 1,
    }


def engage_movement(state: State) -> dict[str, Any]:
    """Execute the actuation movement based on hydraulic pressure."""
    target = state.get("target_position_pct", 0.0)
    pressure = state.get("hydraulic_pressure_psi", 0.0)

    # Simulate movement: if pressure is sufficient, move to target
    moved_to = target if pressure >= 500 else 0.0
    status = "open" if moved_to > 90 else "throttled" if moved_to > 0 else "stalled"

    return {
        "log": [f"{UNISPSC_CODE}:engage_movement - Moving to {moved_to}%"],
        "current_position_pct": moved_to,
        "valve_status": status,
    }


def emit_telemetry(state: State) -> dict[str, Any]:
    """Generate final telemetry and status report for the operation."""
    current = state.get("current_position_pct", 0.0)
    status = state.get("valve_status", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:emit_telemetry - Status: {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "position": current,
                "pressure": state.get("hydraulic_pressure_psi"),
                "cycles": state.get("cycle_count"),
            },
            "status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("calibrate", calibrate_actuator)
_g.add_node("engage", engage_movement)
_g.add_node("telemetry", emit_telemetry)

_g.add_edge(START, "calibrate")
_g.add_edge("calibrate", "engage")
_g.add_edge("engage", "telemetry")
_g.add_edge("telemetry", END)

graph = _g.compile()
