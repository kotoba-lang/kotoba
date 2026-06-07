# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173005 — Plate (segment 25).

Bespoke logic for the "Plate" component agent within the vehicle body and frame
commodity class. This agent handles material validation, dimensional analysis,
and quality certification for structural or identification plates used in
commercial and military vehicles.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173005"
UNISPSC_TITLE = "Plate"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173005"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for structural/vehicle Plate
    material_grade: str
    thickness_mm: float
    surface_treatment: str
    qc_passed: bool


def validate_composition(state: State) -> dict[str, Any]:
    """Verifies the metallurgical grade of the plate material."""
    inp = state.get("input") or {}
    grade = str(inp.get("grade", "Steel-Grade-40"))
    return {
        "log": [f"{UNISPSC_CODE}:validate_composition"],
        "material_grade": grade,
    }


def analyze_geometry(state: State) -> dict[str, Any]:
    """Evaluates thickness and surface finishing specifications."""
    inp = state.get("input") or {}
    thickness = float(inp.get("thickness", 6.35))
    finish = str(inp.get("finish", "Powder-Coated"))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_geometry"],
        "thickness_mm": thickness,
        "surface_treatment": finish,
    }


def certify_component(state: State) -> dict[str, Any]:
    """Performs final compliance check and prepares the component manifest."""
    grade = state.get("material_grade", "Unknown")
    thick = state.get("thickness_mm", 0.0)
    finish = state.get("surface_treatment", "None")

    # Structural integrity heuristic for vehicle plates
    passed = thick >= 1.5 and "Steel" in grade

    return {
        "log": [f"{UNISPSC_CODE}:certify_component"],
        "qc_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "Approved" if passed else "Flagged",
            "specifications": {
                "material": grade,
                "thickness": f"{thick}mm",
                "finish": finish,
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_composition)
_g.add_node("analyze", analyze_geometry)
_g.add_node("certify", certify_component)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
