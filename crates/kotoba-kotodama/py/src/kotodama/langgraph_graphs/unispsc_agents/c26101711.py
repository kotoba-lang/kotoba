# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101711 — Rod.

This bespoke graph manages the specification and validation of electrical or
structural rods within the power generation and distribution segment. It
evaluates material integrity, dimensional compliance, and conductivity metrics.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101711"
UNISPSC_TITLE = "Rod"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101711"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for "Rod"
    material_grade: str
    diameter_mm: float
    length_mm: float
    conductivity_iacs: float
    is_compliant: bool


def validate_dimensions(state: State) -> dict[str, Any]:
    """Ensures the rod dimensions are within power distribution tolerances."""
    inp = state.get("input") or {}
    diameter = float(inp.get("diameter", 0.0))
    length = float(inp.get("length", 0.0))

    # Simple validation logic for a power-segment rod
    valid = diameter > 0 and length > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_dimensions"],
        "diameter_mm": diameter,
        "length_mm": length,
        "is_compliant": valid,
    }


def analyze_material(state: State) -> dict[str, Any]:
    """Evaluates the material properties and conductivity for the rod."""
    inp = state.get("input") or {}
    grade = str(inp.get("material", "Unknown"))

    # Assign a mock conductivity based on grade
    iacs = 101.0 if "copper" in grade.lower() else 61.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_material"],
        "material_grade": grade,
        "conductivity_iacs": iacs,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Finalizes the rod agent execution and produces the result payload."""
    compliance = state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "material": state.get("material_grade"),
                "dimensions": f"{state.get('length_mm')}x{state.get('diameter_mm')}mm",
                "conductivity": state.get("conductivity_iacs"),
            },
            "status": "approved" if compliance else "pending_review",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_dimensions)
_g.add_node("analyze", analyze_material)
_g.add_node("emit", finalize_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
