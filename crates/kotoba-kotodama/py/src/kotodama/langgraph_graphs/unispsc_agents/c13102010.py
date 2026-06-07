# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102010 — Steel (segment 13).
Bespoke logic for steel grade validation, metallurgical verification, and heat traceability.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102010"
UNISPSC_TITLE = "Steel"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102010"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Steel domain logic
    alloy_grade: str
    heat_number: str
    metallurgy_verified: bool
    dimensions_check: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Node: Extract and validate steel specifications from input."""
    inp = state.get("input") or {}
    alloy_grade = inp.get("alloy_grade", "A36")
    heat_number = inp.get("heat_number", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "alloy_grade": alloy_grade,
        "heat_number": heat_number,
        "dimensions_check": "dimensions" in inp
    }


def verify_metallurgy(state: State) -> dict[str, Any]:
    """Node: Verify metallurgical compliance and heat number traceability."""
    alloy = state.get("alloy_grade")
    heat = state.get("heat_number")

    # Simulate metallurgical check against industry standards (e.g. ASTM, AISI)
    valid_grades = {"A36", "1018", "1045", "304", "316", "4140"}
    passed = alloy in valid_grades and heat != "UNKNOWN"

    return {
        "log": [f"{UNISPSC_CODE}:verify_metallurgy:grade={alloy}:passed={passed}"],
        "metallurgy_verified": passed
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Node: Prepare final response with UNISPSC metadata and steel certification status."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "alloy_grade": state.get("alloy_grade"),
            "heat_number": state.get("heat_number"),
            "metallurgy_verified": state.get("metallurgy_verified"),
            "ok": state.get("metallurgy_verified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("verify_metallurgy", verify_metallurgy)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "verify_metallurgy")
_g.add_edge("verify_metallurgy", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
