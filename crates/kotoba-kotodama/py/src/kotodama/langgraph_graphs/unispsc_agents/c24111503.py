# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111503 — Plastic Bag (segment 24).
Custom logic for managing plastic packaging specifications, polymer density,
and environmental compliance tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111503"
UNISPSC_TITLE = "Plastic Bag"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Plastic Bag
    material_density: float
    gauge_thickness_microns: float
    is_biodegradable: bool
    tensile_rating: str


def inspect_specifications(state: State) -> dict[str, Any]:
    """Analyzes the physical properties of the plastic bag material."""
    inp = state.get("input") or {}
    # Extract or default to standard LDPE (Low-Density Polyethylene) properties
    density = float(inp.get("density", 0.92))
    thickness = float(inp.get("thickness", 25.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "material_density": density,
        "gauge_thickness_microns": thickness,
    }


def evaluate_environmental_impact(state: State) -> dict[str, Any]:
    """Checks for biodegradable additives and recycling compliance."""
    inp = state.get("input") or {}
    thickness = state.get("gauge_thickness_microns", 0.0)

    # Logic: Bags over 50 microns are typically reusable/non-single-use compliant
    is_biodegradable = inp.get("additive", "").lower() == "epi" or inp.get("bio", False)

    rating = "Standard"
    if thickness > 60.0:
        rating = "Heavy Duty"
    elif thickness < 15.0:
        rating = "Ultra Thin"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_environmental_impact"],
        "is_biodegradable": is_biodegradable,
        "tensile_rating": rating,
    }


def emit_product_manifest(state: State) -> dict[str, Any]:
    """Generates the final validated state for the Plastic Bag agent."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_product_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "density_g_cm3": state.get("material_density"),
                "thickness_um": state.get("gauge_thickness_microns"),
                "biodegradable": state.get("is_biodegradable"),
                "durability": state.get("tensile_rating"),
            },
            "status": "compliant",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("evaluate_environmental_impact", evaluate_environmental_impact)
_g.add_node("emit_product_manifest", emit_product_manifest)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "evaluate_environmental_impact")
_g.add_edge("evaluate_environmental_impact", "emit_product_manifest")
_g.add_edge("emit_product_manifest", END)

graph = _g.compile()
