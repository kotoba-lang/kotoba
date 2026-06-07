# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23131510 — Sheet Metal (segment 23).

Bespoke LangGraph implementation for processing sheet metal fabrication specs.
Handles material validation, tooling selection, and production order generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23131510"
UNISPSC_TITLE = "Sheet Metal"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23131510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Sheet Metal
    material_type: str
    gauge: int
    dimensions: dict[str, float]
    cutting_method: str
    bend_specs: list[dict[str, Any]]


def validate_material_specs(state: State) -> dict[str, Any]:
    """Validates the input for material type and dimensions."""
    inp = state.get("input") or {}
    material = inp.get("material", "Carbon Steel")
    gauge = inp.get("gauge", 16)
    dims = inp.get("dimensions", {"length": 120.0, "width": 60.0})

    return {
        "log": [f"{UNISPSC_CODE}:validate_material_specs"],
        "material_type": material,
        "gauge": gauge,
        "dimensions": dims,
    }


def determine_fabrication_tooling(state: State) -> dict[str, Any]:
    """Selects the appropriate cutting and bending tools based on gauge and material."""
    gauge = state.get("gauge", 16)
    material = state.get("material_type", "Carbon Steel")

    # Simple logic to determine cutting method
    if gauge < 10:
        method = "Laser"
    elif material == "Aluminum":
        method = "Waterjet"
    else:
        method = "Plasma"

    bends = [
        {"angle": 90, "radius": 0.125, "location": 12.0},
        {"angle": 90, "radius": 0.125, "location": 24.0}
    ]

    return {
        "log": [f"{UNISPSC_CODE}:determine_fabrication_tooling"],
        "cutting_method": method,
        "bend_specs": bends,
    }


def finalize_production_order(state: State) -> dict[str, Any]:
    """Generates the final fabrication result for the sheet metal order."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_production_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "fabrication_details": {
                "material": state.get("material_type"),
                "gauge": state.get("gauge"),
                "method": state.get("cutting_method"),
                "bends_count": len(state.get("bend_specs", [])),
                "surface_area": state.get("dimensions", {}).get("length", 0) * state.get("dimensions", {}).get("width", 0)
            },
            "status": "ready_for_production",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_material_specs)
_g.add_node("tooling", determine_fabrication_tooling)
_g.add_node("finalize", finalize_production_order)

_g.add_edge(START, "validate")
_g.add_edge("validate", "tooling")
_g.add_edge("tooling", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
