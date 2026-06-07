# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122405 — Servo Control (segment 20).

Bespoke logic for managing high-precision servo motor parameters, trajectory
mapping, and safety envelope verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122405"
UNISPSC_TITLE = "Servo Control"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122405"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Servo Control
    target_angle: float
    torque_limit: float
    interpolation_mode: str
    safety_envelope_clear: bool


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates the input move command against the servo's mechanical limits."""
    inp = state.get("input") or {}
    angle = inp.get("angle", 0.0)
    torque = inp.get("torque", 1.0)

    # Ensure angle is within standard robotic arm joint limits (-180 to 180 degrees)
    # and torque is within rated operating range (0 to 2.5 Nm)
    safe = -180.0 <= angle <= 180.0 and 0.0 <= torque <= 2.5

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "target_angle": angle,
        "torque_limit": torque,
        "safety_envelope_clear": safe,
    }


def calculate_motion_path(state: State) -> dict[str, Any]:
    """Determines the interpolation steps required for the desired target angle."""
    # Use different motion profiles based on torque constraints
    torque = state.get("torque_limit", 0.0)
    mode = "linear" if torque > 1.5 else "sinusoidal"

    return {
        "log": [f"{UNISPSC_CODE}:calculate_motion_path"],
        "interpolation_mode": mode,
    }


def execute_servo_command(state: State) -> dict[str, Any]:
    """Finalizes the command packet for delivery to the physical controller."""
    is_safe = state.get("safety_envelope_clear", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "status": "packet_ready" if is_safe else "error_boundary_exceeded",
        "angle": state.get("target_angle"),
        "interpolation": state.get("interpolation_mode"),
        "did": UNISPSC_DID,
        "ok": is_safe,
    }

    return {
        "log": [f"{UNISPSC_CODE}:execute_servo_command"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("compute", calculate_motion_path)
_g.add_node("execute", execute_servo_command)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
