# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151701 — Motor (segment 23).

Bespoke graph logic for motor performance validation and certification.
This module handles specification inspection, load testing simulation,
and final compliance output for industrial motor units.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151701"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for "Motor"
    voltage_rating_v: int
    rated_rpm: int
    efficiency_score: float
    is_certified: bool
    safety_test_passed: bool


def validate_design(state: State) -> dict[str, Any]:
    """Inspects motor design specifications for baseline compliance."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 230)
    rpm = inp.get("rpm", 1750)

    # Simple validation logic
    valid = 100 <= voltage <= 600 and rpm > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_design(voltage={voltage}, rpm={rpm})"],
        "voltage_rating_v": voltage,
        "rated_rpm": rpm,
        "safety_test_passed": valid,
    }


def simulate_load_test(state: State) -> dict[str, Any]:
    """Simulates a load test to determine motor efficiency and thermal stability."""
    if not state.get("safety_test_passed"):
        return {"log": [f"{UNISPSC_CODE}:load_test_skipped_due_to_safety_failure"]}

    # Mock calculation for efficiency score
    voltage = state.get("voltage_rating_v", 230)
    efficiency = 0.85 if voltage > 200 else 0.78

    return {
        "log": [f"{UNISPSC_CODE}:simulate_load_test(efficiency={efficiency:.2f})"],
        "efficiency_score": efficiency,
        "is_certified": efficiency > 0.80,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final result and certification status for the motor unit."""
    is_certified = state.get("is_certified", False)
    safety_pass = state.get("safety_test_passed", False)

    success = is_certified and safety_pass

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification(status={'PASSED' if success else 'FAILED'})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "voltage": state.get("voltage_rating_v"),
                "rpm": state.get("rated_rpm"),
                "efficiency": state.get("efficiency_score"),
            },
            "certification_status": "Active" if success else "Denied",
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_design", validate_design)
_g.add_node("simulate_load_test", simulate_load_test)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "validate_design")
_g.add_edge("validate_design", "simulate_load_test")
_g.add_edge("simulate_load_test", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
