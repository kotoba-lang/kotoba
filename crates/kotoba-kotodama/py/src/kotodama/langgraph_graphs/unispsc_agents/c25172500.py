# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172500 — Tire (segment 25).
Bespoke logic for vehicle tires including specification validation and inventory checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172500"
UNISPSC_TITLE = "Tire"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    rim_diameter: int
    tread_type: str
    psi_rating: int
    inventory_status: str
    validation_passed: bool


def validate_tire_specs(state: State) -> dict[str, Any]:
    """Validates the mechanical specifications of the tire request."""
    inp = state.get("input") or {}
    rim = inp.get("rim_diameter", 0)
    tread = inp.get("tread_type", "all-season")
    psi = inp.get("psi_rating", 32)

    # Simple validation logic for tire safety
    passed = rim > 0 and 10 <= psi <= 120
    return {
        "log": [f"{UNISPSC_CODE}:validate_tire_specs"],
        "rim_diameter": rim,
        "tread_type": tread,
        "psi_rating": psi,
        "validation_passed": passed
    }


def cross_reference_inventory(state: State) -> dict[str, Any]:
    """Simulates checking regional inventory for matching tire dimensions."""
    rim = state.get("rim_diameter", 0)
    # Mock logic: standard even sizes are typically in stock
    stock = "IN_STOCK" if rim > 0 and rim % 2 == 0 else "BACKORDERED"
    if not state.get("validation_passed"):
        stock = "NOT_APPLICABLE"

    return {
        "log": [f"{UNISPSC_CODE}:cross_reference_inventory"],
        "inventory_status": stock
    }


def generate_procurement_data(state: State) -> dict[str, Any]:
    """Finalizes the tire agent execution with a structured procurement result."""
    passed = state.get("validation_passed", False)
    inv = state.get("inventory_status", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:generate_procurement_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "rim_diameter": state.get("rim_diameter"),
                "tread": state.get("tread_type"),
                "psi": state.get("psi_rating")
            },
            "fulfillment": inv,
            "ok": passed and inv == "IN_STOCK",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_tire_specs)
_g.add_node("inventory", cross_reference_inventory)
_g.add_node("emit", generate_procurement_data)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inventory")
_g.add_edge("inventory", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
