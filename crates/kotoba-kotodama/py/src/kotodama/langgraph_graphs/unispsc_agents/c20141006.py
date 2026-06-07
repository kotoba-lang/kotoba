# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141006 — Actuator.
Bespoke implementation for mechanical/electronic movement control systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141006"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141006"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for an Actuator
    actuation_type: str        # e.g., Linear, Rotary, Hydraulic, Pneumatic
    target_position: float     # Target setpoint for the actuator
    current_position: float    # Real-time position feedback
    is_calibrated: bool        # System calibration status
    applied_force: float       # Current force or torque output


def initialize_hardware(state: State) -> dict[str, Any]:
    """Pre-flight check and hardware initialization."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:initialize_hardware"],
        "actuation_type": inp.get("type", "electric_linear"),
        "target_position": float(inp.get("setpoint", 0.0)),
        "current_position": 0.0,
        "is_calibrated": True,
    }


def execute_movement(state: State) -> dict[str, Any]:
    """Translate target setpoints into mechanical motion."""
    target = state.get("target_position", 0.0)
    # Simulate movement physics
    return {
        "log": [f"{UNISPSC_CODE}:execute_movement"],
        "current_position": target,
        "applied_force": 45.2 if state.get("actuation_type") == "hydraulic" else 12.5,
    }


def verify_stowage(state: State) -> dict[str, Any]:
    """Confirm end-stop reach and generate final telemetry."""
    target = state.get("target_position", 0.0)
    current = state.get("current_position", 0.0)
    in_tolerance = abs(target - current) < 0.001

    return {
        "log": [f"{UNISPSC_CODE}:verify_stowage"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "position": current,
                "force": state.get("applied_force"),
                "actuation_type": state.get("actuation_type"),
            },
            "ok": in_tolerance,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_hardware)
_g.add_node("move", execute_movement)
_g.add_node("verify", verify_stowage)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "move")
_g.add_edge("move", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
