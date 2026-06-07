# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101903 — Drum Lifter (segment 24).

This bespoke graph logic handles the operational workflow for drum lifting equipment,
including specification validation, safety load verification, and dispatch emitting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101903"
UNISPSC_TITLE = "Drum Lifter"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Drum Lifter
    lifter_type: str
    weight_capacity_kg: float
    drum_diameter_mm: int
    safety_check_passed: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the industrial specifications for the drum lifter model."""
    inp = state.get("input") or {}
    l_type = inp.get("lifter_type", "hydraulic")
    capacity = float(inp.get("weight_capacity_kg", 300.0))
    diameter = int(inp.get("drum_diameter_mm", 580))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "lifter_type": l_type,
        "weight_capacity_kg": capacity,
        "drum_diameter_mm": diameter,
    }


def verify_load_safety(state: State) -> dict[str, Any]:
    """Calculates safety thresholds based on the lifter type and capacity."""
    capacity = state.get("weight_capacity_kg", 0.0)
    l_type = state.get("lifter_type")

    # Example logic: Manual lifters are restricted below 400kg for safety compliance
    is_passed = True
    if l_type == "manual" and capacity > 400.0:
        is_passed = False

    return {
        "log": [f"{UNISPSC_CODE}:verify_load_safety:passed={is_passed}"],
        "safety_check_passed": is_passed,
    }


def emit_result(state: State) -> dict[str, Any]:
    """Prepares the final actor result and metadata for the Unispsc registry."""
    is_ok = state.get("safety_check_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "operational_certified" if is_ok else "safety_violation",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("safety_check", verify_load_safety)
_g.add_node("emit", emit_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "safety_check")
_g.add_edge("safety_check", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
