# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112405 — Drawer (segment 24).
Bespoke logic for storage and material handling drawer units.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112405"
UNISPSC_TITLE = "Drawer"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112405"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Drawer units
    dimensions_verified: bool
    material_composition: str
    load_rating_kg: float
    locking_mechanism: str
    inspection_passed: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates physical dimensions and material specs of the drawer."""
    inp = state.get("input") or {}
    width = inp.get("width_mm", 0)
    height = inp.get("height_mm", 0)
    material = inp.get("material", "generic_composite")

    # Simple validation: drawer must have positive dimensions
    is_valid = width > 0 and height > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "dimensions_verified": is_valid,
        "material_composition": material,
    }


def analyze_load_capacity(state: State) -> dict[str, Any]:
    """Calculates the load rating based on material and size."""
    material = state.get("material_composition", "generic_composite")
    inp = state.get("input") or {}

    # Heuristic load rating
    base_rating = 10.0
    if material == "reinforced_steel":
        base_rating = 75.0
    elif material == "industrial_plastic":
        base_rating = 25.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_load_capacity"],
        "load_rating_kg": base_rating,
        "locking_mechanism": inp.get("lock_type", "none"),
    }


def certify_unit(state: State) -> dict[str, Any]:
    """Final certification and result emission for the drawer unit."""
    is_valid = state.get("dimensions_verified", False)
    load = state.get("load_rating_kg", 0.0)

    # Certification passes if dimensions are valid and load is sufficient
    passed = is_valid and load > 5.0

    return {
        "log": [f"{UNISPSC_CODE}:certify_unit"],
        "inspection_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": passed,
            "metadata": {
                "material": state.get("material_composition"),
                "load_kg": load,
                "lock": state.get("locking_mechanism"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("analyze", analyze_load_capacity)
_g.add_node("certify", certify_unit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
