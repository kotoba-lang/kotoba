# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121803 — Steel Plate (segment 14).

Bespoke logic for steel plate processing, specification verification,
and theoretical weight calculation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121803"
UNISPSC_TITLE = "Steel Plate"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Steel Plate
    thickness_mm: float
    alloy_grade: str
    surface_treatment: str
    is_galvanized: bool
    theoretical_weight_kg: float


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the steel plate."""
    inp = state.get("input") or {}
    thickness = float(inp.get("thickness", 5.0))
    grade = str(inp.get("grade", "ASTM A36"))
    treatment = str(inp.get("treatment", "Hot Rolled"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "thickness_mm": thickness,
        "alloy_grade": grade,
        "surface_treatment": treatment,
        "is_galvanized": "galvanized" in treatment.lower()
    }


def compute_physical_properties(state: State) -> dict[str, Any]:
    """Computes theoretical weight based on density and dimensions."""
    # Standard steel density approx 7850 kg/m^3
    thickness_mm = state.get("thickness_mm", 5.0)
    thickness_m = thickness_mm / 1000.0
    # Assume a standard 1m x 1m unit area for theoretical weight per unit area
    weight = 1.0 * 1.0 * thickness_m * 7850.0

    return {
        "log": [f"{UNISPSC_CODE}:compute_physical_properties"],
        "theoretical_weight_kg": round(weight, 2)
    }


def prepare_manifest(state: State) -> dict[str, Any]:
    """Prepares the final result manifest for the steel plate agent."""
    weight = state.get("theoretical_weight_kg", 0.0)
    thickness = state.get("thickness_mm", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:prepare_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "data": {
                "thickness_mm": thickness,
                "alloy_grade": state.get("alloy_grade"),
                "treatment": state.get("surface_treatment"),
                "is_galvanized": state.get("is_galvanized"),
                "unit_weight_kg_m2": weight
            },
            "status": "ready" if thickness > 0 else "error"
        }
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("compute_physical_properties", compute_physical_properties)
_g.add_node("prepare_manifest", prepare_manifest)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "compute_physical_properties")
_g.add_edge("compute_physical_properties", "prepare_manifest")
_g.add_edge("prepare_manifest", END)

graph = _g.compile()
