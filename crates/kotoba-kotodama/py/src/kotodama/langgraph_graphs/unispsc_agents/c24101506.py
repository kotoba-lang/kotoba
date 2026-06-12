# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101506 — Cart (segment 24).

Bespoke graph logic for handling material handling equipment specifications,
specifically focused on cart load capacity, material safety, and power configuration.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101506"
UNISPSC_TITLE = "Cart"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    load_capacity_kg: float
    material_safety_verified: bool
    is_motorized: bool
    maintenance_status: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the physical construction specs of the cart."""
    inp = state.get("input") or {}
    material = inp.get("material", "unknown").lower()
    # Industrial carts require verified load-bearing materials
    verified = material in ["steel", "aluminum", "reinforced polymer", "stainless steel"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material_safety_verified": verified,
        "is_motorized": inp.get("power_source") is not None
    }


def assess_load_safety(state: State) -> dict[str, Any]:
    """Calculates safe operating limits based on material verification."""
    inp = state.get("input") or {}
    declared_load = float(inp.get("max_load", 0.0))

    # Safety factor applied if material is not explicitly verified
    if state.get("material_safety_verified"):
        status = "certified"
        capacity = declared_load
    else:
        status = "restricted_use"
        capacity = declared_load * 0.5

    return {
        "log": [f"{UNISPSC_CODE}:assess_load_safety"],
        "load_capacity_kg": capacity,
        "maintenance_status": status
    }


def finalize_cart_registry(state: State) -> dict[str, Any]:
    """Prepares the final actor state and registration metadata."""
    is_ok = state.get("material_safety_verified", False) and state.get("load_capacity_kg", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_cart_registry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "capacity": state.get("load_capacity_kg"),
                "motorized": state.get("is_motorized"),
                "status": state.get("maintenance_status")
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("assess_load_safety", assess_load_safety)
_g.add_node("finalize_cart_registry", finalize_cart_registry)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "assess_load_safety")
_g.add_edge("assess_load_safety", "finalize_cart_registry")
_g.add_edge("finalize_cart_registry", END)

graph = _g.compile()
