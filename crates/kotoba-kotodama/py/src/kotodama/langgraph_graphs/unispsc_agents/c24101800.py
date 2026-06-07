# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101800 — Dock Spec.

Bespoke logic for managing docking equipment specifications, including
structural validation, capacity verification, and site compatibility assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101800"
UNISPSC_TITLE = "Dock Spec"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Dock Spec
    structural_integrity_verified: bool
    dock_dimensions: dict[str, float]
    load_capacity_tons: float
    site_compatibility_rating: int


def validate_engineering_specs(state: State) -> dict[str, Any]:
    """Validates the mechanical and structural specifications of the dock."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {"height": 0.0, "width": 0.0})
    capacity = float(inp.get("capacity", 0.0))

    is_valid = capacity > 0 and dims.get("height", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_engineering_specs"],
        "structural_integrity_verified": is_valid,
        "dock_dimensions": dims,
        "load_capacity_tons": capacity
    }


def assess_site_compatibility(state: State) -> dict[str, Any]:
    """Evaluates if the proposed dock spec fits the installation site constraints."""
    # Logic simulating site fitment based on dimensions
    dims = state.get("dock_dimensions", {})
    height = dims.get("height", 0.0)

    # Simple heuristic: height between 2.5 and 5.0 meters is standard
    rating = 100 if 2.5 <= height <= 5.0 else 50

    return {
        "log": [f"{UNISPSC_CODE}:assess_site_compatibility"],
        "site_compatibility_rating": rating
    }


def finalize_dock_spec(state: State) -> dict[str, Any]:
    """Consolidates the validated specifications into a final actor result."""
    ok = state.get("structural_integrity_verified", False) and state.get("site_compatibility_rating", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dock_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "verified": ok,
            "specs": {
                "dimensions": state.get("dock_dimensions"),
                "capacity": state.get("load_capacity_tons"),
                "compatibility_score": state.get("site_compatibility_rating")
            }
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_engineering_specs)
_g.add_node("assess", assess_site_compatibility)
_g.add_node("finalize", finalize_dock_spec)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
