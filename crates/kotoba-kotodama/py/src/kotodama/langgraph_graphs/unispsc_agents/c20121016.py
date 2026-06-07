# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121016 — Actuator (segment 20).
Bespoke logic for mechanical actuator control and state simulation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121016"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121016"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Actuator
    current_position: float
    target_setpoint: float
    is_homed: bool
    drive_voltage: float
    error_state: str | None


def initialize_hw(state: State) -> dict[str, Any]:
    """Pre-flight check for the actuator hardware state."""
    inp = state.get("input") or {}
    initial_pos = inp.get("initial_position", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:initialize_hw"],
        "current_position": initial_pos,
        "is_homed": inp.get("require_homing", False) is False,
        "error_state": None,
    }


def calculate_stroke(state: State) -> dict[str, Any]:
    """Calculate the mechanical stroke required to reach the target setpoint."""
    inp = state.get("input") or {}
    target = float(inp.get("target", 100.0))

    # Simulate safety clamping for a physical actuator
    clamped_target = max(0.0, min(target, 250.0))
    voltage = 24.0 if clamped_target > state.get("current_position", 0.0) else -24.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_stroke"],
        "target_setpoint": clamped_target,
        "drive_voltage": voltage if clamped_target != state.get("current_position") else 0.0,
    }


def execute_movement(state: State) -> dict[str, Any]:
    """Simulate the physical movement and update final telemetry."""
    target = state.get("target_setpoint", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:execute_movement"],
        "current_position": target,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "final_position": target,
                "homed": state.get("is_homed"),
                "status": "nominal" if not state.get("error_state") else "fault",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_hw)
_g.add_node("calculate", calculate_stroke)
_g.add_node("execute", execute_movement)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "calculate")
_g.add_edge("calculate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
