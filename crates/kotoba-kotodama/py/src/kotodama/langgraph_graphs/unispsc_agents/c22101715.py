# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101715 — Fastener (segment 22).

Bespoke logic for validating and processing industrial fastener specifications,
ensuring material compliance and load-bearing requirements are met.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101715"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101715"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Fasteners
    material_grade: str
    tensile_strength_mpa: float
    safety_check_passed: bool
    batch_id: str


def validate_specification(state: State) -> dict[str, Any]:
    """Validates fastener material grade and dimensions from input."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Standard Steel")
    batch = inp.get("batch", "UNK-000")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification -> {grade}"],
        "material_grade": grade,
        "batch_id": batch,
    }


def calculate_load_tolerance(state: State) -> dict[str, Any]:
    """Simulates calculation of tensile strength based on material grade."""
    grade = state.get("material_grade", "Standard Steel")

    # Simple mapping for internal logic simulation
    strengths = {
        "Grade 5": 825.0,
        "Grade 8": 1034.0,
        "Stainless 304": 505.0,
        "Standard Steel": 400.0
    }
    strength = strengths.get(grade, 350.0)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_tolerance -> {strength} MPa"],
        "tensile_strength_mpa": strength,
    }


def verify_safety_standards(state: State) -> dict[str, Any]:
    """Confirms if the fastener meets the required safety threshold."""
    strength = state.get("tensile_strength_mpa", 0.0)
    # Threshold for safety compliance in this domain model
    passed = strength >= 400.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_standards -> {passed}"],
        "safety_check_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "Certified" if passed else "Rejected",
            "metrics": {
                "material": state.get("material_grade"),
                "tensile_strength": strength,
                "batch": state.get("batch_id")
            }
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("calculate", calculate_load_tolerance)
_g.add_node("verify", verify_safety_standards)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
