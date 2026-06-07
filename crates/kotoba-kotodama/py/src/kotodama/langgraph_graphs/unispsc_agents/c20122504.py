# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122504 — Actuator (segment 20).

Bespoke graph logic for controlling and monitoring physical or logic-based
actuator mechanisms, ensuring signal integrity, calibration, and movement
execution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122504"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields
    control_signal: float
    feedback_value: float
    calibration_status: str
    is_active: bool


def validate_signal(state: State) -> dict[str, Any]:
    """Validates the incoming control signal and system status."""
    inp = state.get("input") or {}
    signal = float(inp.get("signal", 0.0))
    is_valid = 0.0 <= signal <= 100.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_signal: signal={signal} valid={is_valid}"],
        "control_signal": signal,
        "is_active": is_valid
    }


def calibrate_actuator(state: State) -> dict[str, Any]:
    """Ensures the actuator mechanism is zeroed and ready for movement."""
    if not state.get("is_active"):
        return {"log": [f"{UNISPSC_CODE}:calibrate_actuator: skipped"], "calibration_status": "inhibited"}

    # Simulate a calibration sequence
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_actuator: zeroing mechanism"],
        "calibration_status": "calibrated",
        "feedback_value": 0.0
    }


def execute_movement(state: State) -> dict[str, Any]:
    """Translates the control signal into physical or logical displacement."""
    if state.get("calibration_status") != "calibrated":
        return {
            "log": [f"{UNISPSC_CODE}:execute_movement: failed - not calibrated"],
            "result": {"ok": False, "error": "System not calibrated"}
        }

    target = state.get("control_signal", 0.0)
    # Simulate displacement towards target
    return {
        "log": [f"{UNISPSC_CODE}:execute_movement: moving to {target}"],
        "feedback_value": target,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "final_position": target,
            "status": "reached",
            "ok": True
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_signal)
_g.add_node("calibrate", calibrate_actuator)
_g.add_node("execute", execute_movement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calibrate")
_g.add_edge("calibrate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
