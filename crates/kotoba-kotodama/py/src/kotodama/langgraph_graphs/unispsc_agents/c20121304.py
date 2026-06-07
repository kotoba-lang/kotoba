# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121304 — Servo (segment 20).
Bespoke implementation for simulated servo motor actuation and control.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121304"
UNISPSC_TITLE = "Servo"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121304"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Servo control
    target_angle: float
    current_angle: float
    torque_ma: float
    is_calibrated: bool
    status_code: int


def initialize_servo(state: State) -> dict[str, Any]:
    """Initializes the servo state and sets baseline parameters."""
    inp = state.get("input") or {}
    target = float(inp.get("target_angle", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:initialize_servo"],
        "target_angle": target,
        "current_angle": state.get("current_angle", 0.0),
        "is_calibrated": True,
        "status_code": 100,  # Ready
    }


def calculate_actuation(state: State) -> dict[str, Any]:
    """Calculates the torque required to reach the target angle."""
    target = state.get("target_angle", 0.0)
    current = state.get("current_angle", 0.0)
    diff = abs(target - current)

    # Simple torque simulation based on distance to move
    required_torque = diff * 0.5 + 10.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_actuation"],
        "torque_ma": required_torque,
        "status_code": 200,  # Actuating
    }


def finalize_movement(state: State) -> dict[str, Any]:
    """Simulates the completion of the physical movement and logs results."""
    target = state.get("target_angle", 0.0)
    torque = state.get("torque_ma", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_movement_to_{target}"],
        "current_angle": target,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "final_position": target,
            "peak_torque_ma": torque,
            "completion_status": "SUCCESS",
        },
        "status_code": 0,  # Idle
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_servo)
_g.add_node("actuate", calculate_actuation)
_g.add_node("finalize", finalize_movement)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "actuate")
_g.add_edge("actuate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
