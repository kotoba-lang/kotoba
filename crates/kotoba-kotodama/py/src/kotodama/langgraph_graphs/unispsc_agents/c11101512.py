# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101512 — Metal Powder.
This agent handles specifications and quality grading for metallic powders used in
industrial metallurgy and additive manufacturing.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101512"
UNISPSC_TITLE = "Metal Powder"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101512"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Metal Powder
    material_type: str
    purity_level: float
    mesh_size: int
    grade_rating: str


def validate_specs(state: State) -> dict[str, Any]:
    """Extract and validate metal powder specifications from input."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "Unknown Metal"))
    purity = float(inp.get("purity", 0.0))
    mesh = int(inp.get("mesh", 0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material_type": material,
        "purity_level": purity,
        "mesh_size": mesh,
    }


def assess_grade(state: State) -> dict[str, Any]:
    """Determine the quality grade based on purity and mesh size."""
    purity = state.get("purity_level", 0.0)
    mesh = state.get("mesh_size", 0)

    if purity >= 99.9:
        base_grade = "High Purity"
    elif purity >= 95.0:
        base_grade = "Industrial"
    else:
        base_grade = "Scrap/Recycled"

    fineness = "Fine" if mesh >= 325 else "Coarse"
    rating = f"{base_grade} ({fineness})"

    return {
        "log": [f"{UNISPSC_CODE}:assess_grade"],
        "grade_rating": rating,
    }


def generate_certificate(state: State) -> dict[str, Any]:
    """Finalize the analysis and produce the certification result."""
    purity = state.get("purity_level", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:generate_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "material": state.get("material_type"),
            "grade": state.get("grade_rating"),
            "specifications": {
                "purity_pct": purity,
                "mesh_size": state.get("mesh_size"),
            },
            "did": UNISPSC_DID,
            "status": "APPROVED" if purity >= 95.0 else "REJECTED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("assess_grade", assess_grade)
_g.add_node("generate_certificate", generate_certificate)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "assess_grade")
_g.add_edge("assess_grade", "generate_certificate")
_g.add_edge("generate_certificate", END)

graph = _g.compile()
