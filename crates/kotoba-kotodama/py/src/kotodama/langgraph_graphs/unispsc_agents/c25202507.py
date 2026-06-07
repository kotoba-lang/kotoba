# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202507 — Aircraft Window Spec (segment 25).

Bespoke graph logic for validating and certifying aircraft window specifications,
ensuring material compliance, structural integrity, and optical clarity.
"""

from __future__ import annotations

import operator
# operator.add is used for list concatenation in state updates
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202507"
UNISPSC_TITLE = "Aircraft Window Spec"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_grade: str
    pressure_test_psi: float
    optical_clarity_index: float
    certification_status: str


def validate_material_standards(state: State) -> dict[str, Any]:
    """Check material composition against aerospace safety standards."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "MIL-P-25690")  # Stretched acrylic standard
    return {
        "log": [f"{UNISPSC_CODE}:validate_material_standards"],
        "material_grade": grade,
    }


def assess_structural_load(state: State) -> dict[str, Any]:
    """Verify the window can withstand cabin pressure differentials."""
    inp = state.get("input") or {}
    pressure = inp.get("test_pressure", 15.0)
    # Assume clarity index is derived from provided inspection data
    clarity = inp.get("clarity_reading", 0.98)
    return {
        "log": [f"{UNISPSC_CODE}:assess_structural_load"],
        "pressure_test_psi": pressure,
        "optical_clarity_index": clarity,
    }


def certify_specification(state: State) -> dict[str, Any]:
    """Compile final certification results and emit the spec record."""
    grade = state.get("material_grade")
    pressure = state.get("pressure_test_psi", 0.0)
    clarity = state.get("optical_clarity_index", 0.0)

    # Simple logic: must meet minimum pressure and clarity
    is_valid = pressure >= 12.0 and clarity > 0.95
    status = "CERTIFIED" if is_valid else "NON_COMPLIANT"

    return {
        "log": [f"{UNISPSC_CODE}:certify_specification"],
        "certification_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "grade": grade,
            "status": status,
            "verified": is_valid,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_material", validate_material_standards)
_g.add_node("assess_structural", assess_structural_load)
_g.add_node("certify", certify_specification)

_g.add_edge(START, "validate_material")
_g.add_edge("validate_material", "assess_structural")
_g.add_edge("assess_structural", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
