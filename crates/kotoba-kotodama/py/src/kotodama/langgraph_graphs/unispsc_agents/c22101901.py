# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101901 — Actuator (segment 22).

Bespoke logic for controlling and monitoring mechanical actuators, including
parameter validation, calibration sequences, and movement execution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101901"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101901"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Actuator
    calibration_status: str
    target_position: float
    current_position: float
    torque_applied: float
    safety_lock_active: bool


def validate_command(state: State) -> dict[str, Any]:
    """Validates the movement command against safety thresholds."""
    inp = state.get("input") or {}
    target = float(inp.get("target", 0.0))
    limit = float(inp.get("max_torque", 50.0))

    # Check if target is within simulated mechanical limits
    lock = target > 1000.0 or target < -1000.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_command"],
        "target_position": target,
        "torque_applied": 0.0,
        "safety_lock_active": lock,
        "calibration_status": "outdated"
    }


def calibrate_actuator(state: State) -> dict[str, Any]:
    """Performs a simulated zero-point calibration sequence."""
    if state.get("safety_lock_active"):
        return {"log": [f"{UNISPSC_CODE}:calibrate_actuator (skipped - safety lock)"]}

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_actuator (zero-point found)"],
        "calibration_status": "verified",
        "current_position": 0.0
    }


def execute_movement(state: State) -> dict[str, Any]:
    """Simulates the physical movement of the actuator to the target position."""
    if state.get("safety_lock_active"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_movement (aborted)"],
            "current_position": state.get("current_position", 0.0)
        }

    target = state.get("target_position", 0.0)
    simulated_torque = abs(target) * 0.05

    return {
        "log": [f"{UNISPSC_CODE}:execute_movement (position reached)"],
        "current_position": target,
        "torque_applied": simulated_torque
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    """Generates the final actuator status report and telemetry data."""
    is_ok = not state.get("safety_lock_active")

    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_ok,
            "metrics": {
                "final_position": state.get("current_position"),
                "peak_torque": state.get("torque_applied"),
                "calibrated": state.get("calibration_status") == "verified"
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_command)
_g.add_node("calibrate", calibrate_actuator)
_g.add_node("move", execute_movement)
_g.add_node("emit", generate_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calibrate")
_g.add_edge("calibrate", "move")
_g.add_edge("move", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
