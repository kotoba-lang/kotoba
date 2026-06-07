# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20111705"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20111705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Actuator domain fields
    target_displacement: float
    force_torque_limit: float
    safety_lock_engaged: bool
    operational_mode: str
    calibration_status: str


def prepare_actuation(state: State) -> dict[str, Any]:
    """Parse input parameters and initialize the actuator state."""
    inp = state.get("input") or {}
    target = float(inp.get("target", 0.0))
    limit = float(inp.get("limit", 500.0))
    return {
        "log": [f"{UNISPSC_CODE}:prepare_actuation"],
        "target_displacement": target,
        "force_torque_limit": limit,
        "operational_mode": "READY",
        "calibration_status": "PENDING"
    }


def safety_calibration(state: State) -> dict[str, Any]:
    """Verify force limits and engage safety locks if constraints are violated."""
    limit = state.get("force_torque_limit", 0.0)
    # Engage safety lock if requested force torque exceeds safe operating threshold
    lock = limit > 1000.0
    return {
        "log": [f"{UNISPSC_CODE}:safety_calibration"],
        "safety_lock_engaged": lock,
        "calibration_status": "VERIFIED" if not lock else "FAULT",
        "operational_mode": "SAFE" if lock else "ACTIVE"
    }


def execute_movement(state: State) -> dict[str, Any]:
    """Perform mechanical movement if safety and calibration checks pass."""
    locked = state.get("safety_lock_engaged", False)
    status = state.get("calibration_status")

    if locked or status == "FAULT":
        res = {
            "ok": False,
            "error": "Safety lock engaged or calibration fault: Force limit exceeded"
        }
    else:
        res = {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "displacement_achieved": state.get("target_displacement"),
            "ok": True,
        }

    return {
        "log": [f"{UNISPSC_CODE}:execute_movement"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("prepare", prepare_actuation)
_g.add_node("calibrate", safety_calibration)
_g.add_node("execute", execute_movement)

_g.add_edge(START, "prepare")
_g.add_edge("prepare", "calibrate")
_g.add_edge("calibrate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
