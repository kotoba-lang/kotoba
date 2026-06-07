# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101754 — Valve (segment 26).

Bespoke logic for industrial valve specification validation and lifecycle
management. Handles integrity verification and actuation status checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101754"
UNISPSC_TITLE = "Valve"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101754"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain state for Valve
    specs_validated: bool
    pressure_test_passed: bool
    seal_integrity: float
    actuator_type: str
    is_operational: bool


def validate_configuration(state: State) -> dict[str, Any]:
    """Validates the valve configuration and material specifications."""
    inp = state.get("input") or {}
    has_specs = "pressure_rating" in inp and "material" in inp

    return {
        "log": [f"{UNISPSC_CODE}:validate_configuration"],
        "specs_validated": has_specs,
        "actuator_type": inp.get("actuator", "manual"),
    }


def conduct_pressure_test(state: State) -> dict[str, Any]:
    """Simulates a pressure integrity test for the valve assembly."""
    validated = state.get("specs_validated", False)
    # Mocking a test result based on validation status
    test_score = 0.99 if validated else 0.45

    return {
        "log": [f"{UNISPSC_CODE}:conduct_pressure_test"],
        "seal_integrity": test_score,
        "pressure_test_passed": test_score > 0.90,
    }


def finalize_valve_state(state: State) -> dict[str, Any]:
    """Emits the final validated state of the Valve agent."""
    passed = state.get("pressure_test_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_valve_state"],
        "is_operational": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if passed else "FAILED_INSPECTION",
            "metadata": {
                "seal_integrity": state.get("seal_integrity"),
                "actuator": state.get("actuator_type")
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_configuration)
_g.add_node("test", conduct_pressure_test)
_g.add_node("finalize", finalize_valve_state)

_g.add_edge(START, "validate")
_g.add_edge("validate", "test")
_g.add_edge("test", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
