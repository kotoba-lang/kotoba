# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24121509 — Packaging (segment 24).
Bespoke logic for packaging specification validation, material grading, and compliance auditing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24121509"
UNISPSC_TITLE = "Packaging"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24121509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Packaging
    package_type: str
    material_grade: str
    dimensions_verified: bool
    gross_weight_kg: float
    hazard_class: int


def validate_dimensions(state: State) -> dict[str, Any]:
    """Validates that dimensions and weight are provided for the package."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {})
    weight = inp.get("weight", 0.0)

    # Check for presence of length, width, and height
    verified = all(k in dims for k in ("l", "w", "h"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_dimensions"],
        "dimensions_verified": verified,
        "gross_weight_kg": float(weight),
        "package_type": inp.get("type", "corrugated_box")
    }


def select_material_grade(state: State) -> dict[str, Any]:
    """Determines appropriate material grade based on weight and package type."""
    weight = state.get("gross_weight_kg", 0.0)
    p_type = state.get("package_type", "corrugated_box")

    # Simple logic for material grading
    grade = "Standard"
    if weight > 20.0:
        grade = "Double-Wall Reinforced"
    if "crate" in p_type.lower() or weight > 100.0:
        grade = "Industrial Timber/Steel"

    return {
        "log": [f"{UNISPSC_CODE}:select_material_grade"],
        "material_grade": grade,
        "hazard_class": int(state.get("input", {}).get("hazard_class", 0))
    }


def generate_packaging_spec(state: State) -> dict[str, Any]:
    """Produces the final packaging specification result and manifest entry."""
    is_valid = state.get("dimensions_verified", False)
    grade = state.get("material_grade", "Standard")
    h_class = state.get("hazard_class", 0)

    # Final compliance check
    compliant = is_valid and (h_class == 0 or grade != "Standard")

    return {
        "log": [f"{UNISPSC_CODE}:generate_packaging_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "material_grade": grade,
                "hazard_rating": h_class,
                "verified": is_valid,
                "status": "approved" if compliant else "rejected_due_to_non_compliance"
            },
            "ok": compliant
        }
    }


_g = StateGraph(State)
_g.add_node("validate_dimensions", validate_dimensions)
_g.add_node("select_material_grade", select_material_grade)
_g.add_node("generate_packaging_spec", generate_packaging_spec)

_g.add_edge(START, "validate_dimensions")
_g.add_edge("validate_dimensions", "select_material_grade")
_g.add_edge("select_material_grade", "generate_packaging_spec")
_g.add_edge("generate_packaging_spec", END)

graph = _g.compile()
