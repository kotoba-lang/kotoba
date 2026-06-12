# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141509 — Rubber Cord (segment 24).

Bespoke LangGraph implementation for Rubber Cord processing, providing
automated inspection, specification analysis, and certification logic.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141509"
UNISPSC_TITLE = "Rubber Cord"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    diameter_mm: float
    material_type: str
    tensile_strength_rating: int
    is_compliant: bool


def inspect_dimensions(state: State) -> dict[str, Any]:
    """Validates the input dimensions and material composition."""
    inp = state.get("input") or {}
    diameter = float(inp.get("diameter", 3.175))  # Default 1/8 inch
    material = str(inp.get("material", "EPDM"))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_dimensions"],
        "diameter_mm": diameter,
        "material_type": material,
    }


def calculate_capabilities(state: State) -> dict[str, Any]:
    """Determines tensile strength and compliance based on material properties."""
    material = state.get("material_type", "Unknown").lower()
    diameter = state.get("diameter_mm", 0.0)

    # Heuristic: Natural rubber has higher base strength than synthetic in this mock
    base_strength = 200 if "natural" in material else 150
    final_rating = int(base_strength * (diameter / 3.0))

    return {
        "log": [f"{UNISPSC_CODE}:calculate_capabilities"],
        "tensile_strength_rating": final_rating,
        "is_compliant": diameter > 0.5 and final_rating > 50,
    }


def certify_product(state: State) -> dict[str, Any]:
    """Generates the final certificate and result payload."""
    compliant = state.get("is_compliant", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_product"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "diameter_mm": state.get("diameter_mm"),
                "material": state.get("material_type"),
                "tensile_rating": state.get("tensile_strength_rating"),
            },
            "certified": compliant,
            "status": "PASS" if compliant else "FAIL",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_dimensions)
_g.add_node("analyze", calculate_capabilities)
_g.add_node("certify", certify_product)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
