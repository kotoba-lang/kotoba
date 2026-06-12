# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121419 — Actuator (segment 20).

Bespoke graph logic for mechanical actuation control systems. This agent
handles calibration, signal verification, and movement execution for
industrial actuators, ensuring mechanical limits and safety constraints
are respected during state transitions.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121419"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121419"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for Actuator
    signal_input: float
    position_feedback: float
    is_calibrated: bool
    safety_lock: bool
    limit_reached: bool


def calibrate(state: State) -> dict[str, Any]:
    """Ensure the actuator is zeroed and ready for operation."""
    return {
        "log": [f"{UNISPSC_CODE}:calibrate - performing home routine"],
        "is_calibrated": True,
        "position_feedback": 0.0,
        "safety_lock": False,
    }


def verify_signal(state: State) -> dict[str, Any]:
    """Check if the incoming control signal is within safe operating parameters."""
    inp = state.get("input") or {}
    signal = float(inp.get("target_signal", 0.0))

    # Industrial safety check: signal must be between 0.0 and 100.0 (e.g. 0-10V or 4-20mA range)
    is_safe = 0.0 <= signal <= 100.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_signal - input {signal} {'accepted' if is_safe else 'REJECTED'}"],
        "signal_input": signal,
        "safety_lock": not is_safe,
    }


def execute_actuation(state: State) -> dict[str, Any]:
    """Apply the control signal to the mechanical component and update feedback."""
    if state.get("safety_lock"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_actuation - ABORTED: safety lock active"],
            "result": {"status": "error", "error_code": "SIGNAL_OUT_OF_RANGE", "ok": False},
        }

    if not state.get("is_calibrated"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_actuation - ABORTED: calibration required"],
            "result": {"status": "error", "error_code": "NOT_CALIBRATED", "ok": False},
        }

    target = state.get("signal_input", 0.0)
    at_limit = target >= 100.0 or target <= 0.0

    return {
        "log": [f"{UNISPSC_CODE}:execute_actuation - moving to {target}% stroke"],
        "position_feedback": target,
        "limit_reached": at_limit,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "final_position": target,
            "limit_warning": at_limit,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("calibrate", calibrate)
_g.add_node("verify_signal", verify_signal)
_g.add_node("execute_actuation", execute_actuation)

_g.add_edge(START, "calibrate")
_g.add_edge("calibrate", "verify_signal")
_g.add_edge("verify_signal", "execute_actuation")
_g.add_edge("execute_actuation", END)

graph = _g.compile()
