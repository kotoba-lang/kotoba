# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101721 — Trolley lid (segment 24).

Bespoke graph logic for validating trolley lid specifications, material
compatibility, and hygiene requirements for material handling equipment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101721"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101721"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    lid_material: str
    dimensions_mm: dict[str, float]
    compatibility_rating: float
    is_food_safe: bool


def inspect_specs(state: State) -> dict[str, Any]:
    """Inspects the physical specifications provided in the input."""
    inp = state.get("input") or {}
    material = inp.get("material", "polypropylene")
    dims = inp.get("dimensions", {"length": 600.0, "width": 400.0})

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs -> {material}"],
        "lid_material": material,
        "dimensions_mm": dims,
    }


def analyze_compliance(state: State) -> dict[str, Any]:
    """Analyzes material compliance for specific industrial or food-grade usage."""
    material = state.get("lid_material", "").lower()
    # High-density polyethylene and polypropylene are generally food-safe
    food_safe = material in ["hdpe", "polypropylene", "stainless steel"]

    return {
        "log": [f"{UNISPSC_CODE}:analyze_compliance -> food_safe={food_safe}"],
        "is_food_safe": food_safe,
    }


def verify_fitment(state: State) -> dict[str, Any]:
    """Verifies if the lid dimensions match standard transport trolley sizes."""
    dims = state.get("dimensions_mm", {})
    l, w = dims.get("length", 0), dims.get("width", 0)

    # Common Euro-standard sizes for trolleys and crates
    if (l == 600 and w == 400) or (l == 400 and w == 300):
        rating = 1.0
    elif l == 800 and w == 600:
        rating = 0.9
    else:
        rating = 0.5

    return {
        "log": [f"{UNISPSC_CODE}:verify_fitment -> rating {rating}"],
        "compatibility_rating": rating,
    }


def emit_result(state: State) -> dict[str, Any]:
    """Finalizes the asset verification record for the trolley lid."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "attributes": {
                "material": state.get("lid_material"),
                "dimensions": state.get("dimensions_mm"),
                "food_safe": state.get("is_food_safe"),
            },
            "verification_score": state.get("compatibility_rating", 0.0),
            "status": "approved" if state.get("compatibility_rating", 0) > 0.8 else "review_required",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specs", inspect_specs)
_g.add_node("analyze_compliance", analyze_compliance)
_g.add_node("verify_fitment", verify_fitment)
_g.add_node("emit_result", emit_result)

_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "analyze_compliance")
_g.add_edge("analyze_compliance", "verify_fitment")
_g.add_edge("verify_fitment", "emit_result")
_g.add_edge("emit_result", END)

graph = _g.compile()
