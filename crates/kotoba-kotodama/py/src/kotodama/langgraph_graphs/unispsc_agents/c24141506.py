# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141506 — Tarpaulin (segment 24).
Bespoke implementation for material processing and inventory state.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141506"
UNISPSC_TITLE = "Tarpaulin"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Tarpaulin
    material_type: str
    surface_area: float
    waterproof_rating: int
    reinforcement_edges: bool


def inspect_material(state: State) -> dict[str, Any]:
    """Node: Validate material composition and dimensions."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "polyethylene"))
    area = float(inp.get("area", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_material -> {material} ({area}m2)"],
        "material_type": material,
        "surface_area": area,
    }


def assess_protection(state: State) -> dict[str, Any]:
    """Node: Determine waterproof rating based on material type."""
    material = state.get("material_type", "polyethylene")

    # Simple logic mapping material to a rating (1-10)
    ratings = {
        "vinyl": 9,
        "canvas": 7,
        "polyethylene": 6,
        "mesh": 2
    }
    rating = ratings.get(material.lower(), 5)

    return {
        "log": [f"{UNISPSC_CODE}:assess_protection -> rating {rating}"],
        "waterproof_rating": rating,
        "reinforcement_edges": rating > 5,
    }


def catalog_item(state: State) -> dict[str, Any]:
    """Node: Finalize result and catalog the tarpaulin unit."""
    return {
        "log": [f"{UNISPSC_CODE}:catalog_item"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "material": state.get("material_type"),
                "area": state.get("surface_area"),
                "waterproof_rating": state.get("waterproof_rating"),
                "reinforced": state.get("reinforcement_edges"),
            },
            "status": "verified",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_material", inspect_material)
_g.add_node("assess_protection", assess_protection)
_g.add_node("catalog_item", catalog_item)

_g.add_edge(START, "inspect_material")
_g.add_edge("inspect_material", "assess_protection")
_g.add_edge("assess_protection", "catalog_item")
_g.add_edge("catalog_item", END)

graph = _g.compile()
