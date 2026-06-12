# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112504 — Box (segment 24).

Bespoke graph implementing structural specification and load-bearing
analysis for industrial and commercial boxing solutions.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112504"
UNISPSC_TITLE = "Box"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    dimensions_mm: dict[str, float]
    material_type: str
    max_weight_capacity_kg: float
    is_eco_friendly: bool


def define_geometry(state: State) -> dict[str, Any]:
    """Extracts and validates box dimensions from the input payload."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {"length": 300, "width": 200, "height": 200})
    material = inp.get("material", "corrugated_fiberboard")

    return {
        "log": [f"{UNISPSC_CODE}:define_geometry"],
        "dimensions_mm": dims,
        "material_type": material,
        "is_eco_friendly": "fiberboard" in material or "cardboard" in material
    }


def analyze_structural_limit(state: State) -> dict[str, Any]:
    """Calculates weight capacity based on volume and material density."""
    dims = state.get("dimensions_mm", {})
    volume = (dims.get("length", 0) * dims.get("width", 0) * dims.get("height", 0)) / 1_000_000
    material = state.get("material_type", "standard")

    # Heuristic: Fiberboard supports ~15kg per 0.1 m3, Wood supports ~50kg
    base_factor = 150 if "fiberboard" in material else 500
    capacity = volume * base_factor

    return {
        "log": [f"{UNISPSC_CODE}:analyze_structural_limit"],
        "max_weight_capacity_kg": round(capacity, 2)
    }


def certify_specification(state: State) -> dict[str, Any]:
    """Finalizes the technical data sheet for the specific box actor."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "dimensions": state.get("dimensions_mm"),
                "material": state.get("material_type"),
                "max_load_kg": state.get("max_weight_capacity_kg"),
                "eco_certified": state.get("is_eco_friendly")
            },
            "status": "certified"
        },
    }


_g = StateGraph(State)
_g.add_node("define_geometry", define_geometry)
_g.add_node("analyze_structural_limit", analyze_structural_limit)
_g.add_node("certify_specification", certify_specification)

_g.add_edge(START, "define_geometry")
_g.add_edge("define_geometry", "analyze_structural_limit")
_g.add_edge("analyze_structural_limit", "certify_specification")
_g.add_edge("certify_specification", END)

graph = _g.compile()
