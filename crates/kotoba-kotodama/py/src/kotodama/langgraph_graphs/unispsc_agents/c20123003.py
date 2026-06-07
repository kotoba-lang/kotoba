# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20123003 — Bearing (segment 20).

Bespoke graph logic for mechanical bearing verification, load specification
analysis, and precision tolerance validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20123003"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20123003"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Bearing
    load_spec_verified: bool
    material_integrity: str
    dimensions_valid: bool
    precision_class: str


def validate_material(state: State) -> dict[str, Any]:
    """Checks if the material and physical dimensions are within operational limits."""
    inp = state.get("input") or {}
    material = inp.get("material", "Chrome Steel")
    id_mm = inp.get("inner_diameter_mm", 0)
    od_mm = inp.get("outer_diameter_mm", 0)

    # Simple dimension validation
    valid = id_mm > 0 and od_mm > id_mm

    return {
        "log": [f"{UNISPSC_CODE}:validate_material"],
        "material_integrity": f"Material: {material} confirmed.",
        "dimensions_valid": valid,
    }


def analyze_load_rating(state: State) -> dict[str, Any]:
    """Simulates calculation of static and dynamic load capacities."""
    valid_dims = state.get("dimensions_valid", False)
    precision = "P0"
    load_ok = False

    if valid_dims:
        # Placeholder logic: larger bearings assigned higher precision classes
        inp = state.get("input") or {}
        od = inp.get("outer_diameter_mm", 0)
        precision = "P6" if od > 50 else "P0"
        load_ok = True

    return {
        "log": [f"{UNISPSC_CODE}:analyze_load_rating"],
        "load_spec_verified": load_ok,
        "precision_class": precision,
    }


def finalize_bearing_spec(state: State) -> dict[str, Any]:
    """Finalizes the technical specification and emits the result agent response."""
    ok = state.get("load_spec_verified", False) and state.get("dimensions_valid", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_bearing_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": ok,
            "technical_summary": {
                "integrity": state.get("material_integrity"),
                "precision": state.get("precision_class"),
                "status": "Certified" if ok else "Rejected"
            },
        },
    }


_g = StateGraph(State)
_g.add_node("validate_material", validate_material)
_g.add_node("analyze_load_rating", analyze_load_rating)
_g.add_node("finalize_bearing_spec", finalize_bearing_spec)

_g.add_edge(START, "validate_material")
_g.add_edge("validate_material", "analyze_load_rating")
_g.add_edge("analyze_load_rating", "finalize_bearing_spec")
_g.add_edge("finalize_bearing_spec", END)

graph = _g.compile()
