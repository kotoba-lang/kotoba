# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101600 — Component (segment 22).

Bespoke logic for managing construction machinery components, verifying
specifications, compatibility, and inventory status within the Etz Hayyim
actor mesh.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101600"
UNISPSC_TITLE = "Component"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for construction components
    specification_verified: bool
    compatibility_rating: float
    inventory_bin: str
    certification_check: str


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the component specifications against engineering benchmarks."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})
    # Simulation: Require material and tolerance declarations for compliance
    is_valid = bool(specs and "material" in specs and "tolerance" in specs)
    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "specification_verified": is_valid,
    }


def assess_compatibility(state: State) -> dict[str, Any]:
    """Assesses mechanical compatibility with machinery interface standards."""
    inp = state.get("input") or {}
    mount_type = inp.get("mount_type", "standard")
    # Higher rating for recognized ISO interfaces in segment 22
    rating = 0.98 if mount_type == "ISO-3471" else 0.82
    return {
        "log": [f"{UNISPSC_CODE}:assess_compatibility"],
        "compatibility_rating": rating,
        "certification_check": "Certified" if rating > 0.9 else "Pending Inspection",
    }


def allocate_inventory(state: State) -> dict[str, Any]:
    """Assigns storage location based on verification and certification status."""
    verified = state.get("specification_verified", False)
    certified = state.get("certification_check") == "Certified"

    if verified and certified:
        bin_id = "ZONE-22-ALPHA"
    elif verified:
        bin_id = "ZONE-22-BETA"
    else:
        bin_id = "QUARANTINE-STAGING"

    return {
        "log": [f"{UNISPSC_CODE}:allocate_inventory"],
        "inventory_bin": bin_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "Ready" if certified else "Hold",
            "allocation": bin_id,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_spec", validate_spec)
_g.add_node("assess_compatibility", assess_compatibility)
_g.add_node("allocate_inventory", allocate_inventory)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "assess_compatibility")
_g.add_edge("assess_compatibility", "allocate_inventory")
_g.add_edge("allocate_inventory", END)

graph = _g.compile()
