# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122827 — Actuator (segment 20).

Bespoke graph logic for actuator control and monitoring.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122827"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122827"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Actuator
    mechanical_state: str
    calibration_status: bool
    target_position: float
    current_position: float
    torque_limit: float


def validate_setpoint(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    target = float(inp.get("target_position", 0.0))
    limit = float(inp.get("torque_limit", 100.0))

    # Simple validation logic: target must be within operational range
    is_valid = 0.0 <= target <= 1000.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_setpoint - target: {target}, valid: {is_valid}"],
        "target_position": target,
        "torque_limit": limit,
        "mechanical_state": "idle",
        "calibration_status": True,
    }


def execute_movement(state: State) -> dict[str, Any]:
    target = state.get("target_position", 0.0)
    # Simulating movement transition in state
    return {
        "log": [f"{UNISPSC_CODE}:execute_movement - moving to position {target}"],
        "mechanical_state": "moving",
        "current_position": target,
    }


def verify_position(state: State) -> dict[str, Any]:
    current = state.get("current_position", 0.0)
    target = state.get("target_position", 0.0)
    # Verify target was reached within tolerance
    success = abs(current - target) < 0.001

    return {
        "log": [f"{UNISPSC_CODE}:verify_position - final position: {current}, success: {success}"],
        "mechanical_state": "idle",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": success,
            "final_position": current,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_setpoint)
_g.add_node("execute", execute_movement)
_g.add_node("verify", verify_position)

_g.add_edge(START, "validate")
_g.add_edge("validate", "execute")
_g.add_edge("execute", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
