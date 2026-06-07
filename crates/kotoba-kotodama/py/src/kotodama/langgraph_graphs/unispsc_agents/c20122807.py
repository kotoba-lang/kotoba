# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122807 — Actuator (segment 20).

This module provides bespoke logic for the Actuator agent, handling
positioning, calibration verification, and mechanical execution
state transitions.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122807"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122807"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    target_position_mm: float
    current_position_mm: float
    is_calibrated: bool
    force_load_newton: float


def parse_instruction(state: State) -> dict[str, Any]:
    """Extracts target parameters from the input command."""
    inp = state.get("input") or {}
    target = float(inp.get("target_position", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:parse_instruction -> {target}mm"],
        "target_position_mm": target,
        "current_position_mm": state.get("current_position_mm", 0.0),
    }


def verify_alignment(state: State) -> dict[str, Any]:
    """Simulates checking internal feedback sensors for calibration."""
    # Logic: Actuator must be calibrated before motion
    is_ok = state.get("target_position_mm", 0.0) >= 0.0
    return {
        "log": [f"{UNISPSC_CODE}:verify_alignment -> {is_ok}"],
        "is_calibrated": is_ok,
        "force_load_newton": 15.5 if is_ok else 0.0,
    }


def execute_motion(state: State) -> dict[str, Any]:
    """Updates the position to match the target if calibrated."""
    calibrated = state.get("is_calibrated", False)
    target = state.get("target_position_mm", 0.0)

    new_pos = target if calibrated else state.get("current_position_mm", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:execute_motion"],
        "current_position_mm": new_pos,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "position": new_pos,
            "status": "completed" if calibrated else "error_uncalibrated",
            "ok": calibrated,
        },
    }


_g = StateGraph(State)

_g.add_node("parse", parse_instruction)
_g.add_node("verify", verify_alignment)
_g.add_node("execute", execute_motion)

_g.add_edge(START, "parse")
_g.add_edge("parse", "verify")
_g.add_edge("verify", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
