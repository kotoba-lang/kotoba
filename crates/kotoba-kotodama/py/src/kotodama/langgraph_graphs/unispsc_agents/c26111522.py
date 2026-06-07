# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111522 — Pusher (segment 26).
Power transmission component responsible for mechanical actuation and force delivery.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111522"
UNISPSC_TITLE = "Pusher"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111522"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for a mechanical Pusher
    stroke_length_mm: float
    target_force_newtons: float
    actual_position_mm: float
    safety_interlock_active: bool
    operation_status: str


def initialize_actuator(state: State) -> dict[str, Any]:
    """Calibrates the pusher and sets target parameters from input."""
    inp = state.get("input") or {}
    target_stroke = float(inp.get("stroke", 50.0))
    target_force = float(inp.get("force", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_actuator -> Target: {target_stroke}mm @ {target_force}N"],
        "stroke_length_mm": target_stroke,
        "target_force_newtons": target_force,
        "safety_interlock_active": True,
        "operation_status": "CALIBRATED",
    }


def execute_stroke(state: State) -> dict[str, Any]:
    """Simulates the physical movement of the pusher to the target position."""
    # Logic: Assume movement is successful if safety is active
    if state.get("safety_interlock_active"):
        target = state.get("stroke_length_mm", 0.0)
        return {
            "log": [f"{UNISPSC_CODE}:execute_stroke -> Moving to {target}mm"],
            "actual_position_mm": target,
            "operation_status": "POSITION_REACHED",
        }
    return {
        "log": [f"{UNISPSC_CODE}:execute_stroke -> Safety fault"],
        "operation_status": "FAULT",
    }


def finalize_transmission(state: State) -> dict[str, Any]:
    """Validates the actuation and packages the result."""
    status = state.get("operation_status")
    pos = state.get("actual_position_mm", 0.0)
    success = status == "POSITION_REACHED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_transmission -> Final Status: {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "stroke_verified": success,
            "final_position": pos,
            "status": status,
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_actuator)
_g.add_node("actuate", execute_stroke)
_g.add_node("finalize", finalize_transmission)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "actuate")
_g.add_edge("actuate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
