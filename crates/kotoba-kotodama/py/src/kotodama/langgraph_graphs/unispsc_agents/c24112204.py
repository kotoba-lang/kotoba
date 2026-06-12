# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112204 — Pail (segment 24).

Bespoke graph logic for containerizing materials in pails. This agent handles
specification validation, quality assurance for leak-proofing and handle
durability, and final batch certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112204"
UNISPSC_TITLE = "Pail"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112204"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Pail containers
    capacity_liters: float
    material_type: str
    leak_test_passed: bool
    handle_integrity_score: float
    is_food_grade: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and material specs of the pail."""
    inp = state.get("input") or {}
    capacity = float(inp.get("capacity", 20.0))
    material = inp.get("material", "HDPE")
    food_grade = inp.get("food_grade", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "capacity_liters": capacity,
        "material_type": material,
        "is_food_grade": food_grade,
    }


def perform_qa_testing(state: State) -> dict[str, Any]:
    """Simulates leak-proof testing and handle stress analysis."""
    material = state.get("material_type", "Unknown")

    # Logic: Plastic pails generally pass leak tests; metal depends on seam
    leak_passed = True if material in ["HDPE", "PP", "Steel"] else False

    # Logic: Calculate a dummy integrity score based on capacity
    capacity = state.get("capacity_liters", 0.0)
    integrity = 0.95 if capacity <= 25.0 else 0.88

    return {
        "log": [f"{UNISPSC_CODE}:perform_qa_testing"],
        "leak_test_passed": leak_passed,
        "handle_integrity_score": integrity,
    }


def certify_output(state: State) -> dict[str, Any]:
    """Produces the final container certification and result payload."""
    is_valid = state.get("leak_test_passed", False) and state.get("handle_integrity_score", 0.0) > 0.8

    return {
        "log": [f"{UNISPSC_CODE}:certify_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_valid,
            "specs": {
                "volume": state.get("capacity_liters"),
                "material": state.get("material_type"),
                "food_safe": state.get("is_food_grade")
            },
            "status": "ready_for_shipment" if is_valid else "rejected_qa"
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specification", validate_specification)
_g.add_node("perform_qa_testing", perform_qa_testing)
_g.add_node("certify_output", certify_output)

_g.add_edge(START, "validate_specification")
_g.add_edge("validate_specification", "perform_qa_testing")
_g.add_edge("perform_qa_testing", "certify_output")
_g.add_edge("certify_output", END)

graph = _g.compile()
