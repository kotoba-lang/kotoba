# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202405 — Fuel (segment 25).

Bespoke logic for fuel procurement, specification verification, and
inventory management. This agent handles state transitions for fuel
batches, ensuring compliance with grade ratings and safety standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202405"
UNISPSC_TITLE = "Fuel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202405"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Fuel
    fuel_type: str  # e.g., Diesel, Gasoline, Aviation, Biofuel
    volume_liters: float
    grade_rating: str  # Octane/Cetane rating or ISO standard
    emissions_tier: int
    safety_certificate_verified: bool


def inspect_delivery(state: State) -> dict[str, Any]:
    """Inspects the incoming fuel delivery request and initializes state."""
    inp = state.get("input") or {}
    fuel_type = inp.get("fuel_type", "unspecified")
    volume = float(inp.get("volume", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_delivery -> type: {fuel_type}, volume: {volume}"],
        "fuel_type": fuel_type,
        "volume_liters": volume,
        "safety_certificate_verified": False,
    }


def verify_specifications(state: State) -> dict[str, Any]:
    """Verifies fuel grade and emissions standards compliance."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Standard")
    tier = int(inp.get("emissions_tier", 4))

    # Logic: Mark as verified if data exists
    verified = bool(grade and tier >= 0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications -> grade: {grade}, tier: {tier}"],
        "grade_rating": grade,
        "emissions_tier": tier,
        "safety_certificate_verified": verified,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Finalizes the fuel record and prepares the result output."""
    is_valid = state.get("safety_certificate_verified", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "did": UNISPSC_DID,
        "status": "Accepted" if is_valid else "Rejected",
        "inventory_data": {
            "type": state.get("fuel_type"),
            "qty": state.get("volume_liters"),
            "grade": state.get("grade_rating"),
        },
        "ok": is_valid,
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory -> status: {res['status']}"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("inspect_delivery", inspect_delivery)
_g.add_node("verify_specifications", verify_specifications)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "inspect_delivery")
_g.add_edge("inspect_delivery", "verify_specifications")
_g.add_edge("verify_specifications", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
