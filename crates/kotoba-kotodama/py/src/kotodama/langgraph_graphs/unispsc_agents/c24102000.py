# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102000 — Shelf (segment 24).
Bespoke graph logic for industrial shelf asset management and structural validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102000"
UNISPSC_TITLE = "Shelf"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Shelf
    material_composition: str
    max_load_capacity_kg: float
    dimensions_mm: dict[str, float]
    safety_certification: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Inspects input for required shelf specifications and material data."""
    inp = state.get("input") or {}
    material = inp.get("material", "Industrial Steel")
    dims = inp.get("dimensions", {"width": 1200, "depth": 600, "height": 40})

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material_composition": material,
        "dimensions_mm": dims,
        "safety_certification": False
    }


def compute_load_rating(state: State) -> dict[str, Any]:
    """Calculates safe load capacity based on material and shelf dimensions."""
    material = state.get("material_composition", "Unknown")
    dims = state.get("dimensions_mm", {})

    # Heuristic calculation for bespoke shelf logic
    base_load = 50.0
    if "Steel" in material:
        base_load = 250.0
    elif "Wood" in material:
        base_load = 100.0

    width_factor = dims.get("width", 1000) / 1000.0
    load_capacity = base_load * width_factor

    return {
        "log": [f"{UNISPSC_CODE}:compute_load_rating"],
        "max_load_capacity_kg": load_capacity,
        "safety_certification": load_capacity > 0
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Generates the final registry entry for the shelf unit."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "material": state.get("material_composition"),
                "load_limit": state.get("max_load_capacity_kg"),
                "certified": state.get("safety_certification")
            },
            "status": "ready_for_deployment"
        }
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("compute_load_rating", compute_load_rating)
_g.add_node("finalize_asset_record", finalize_asset_record)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "compute_load_rating")
_g.add_edge("compute_load_rating", "finalize_asset_record")
_g.add_edge("finalize_asset_record", END)

graph = _g.compile()
