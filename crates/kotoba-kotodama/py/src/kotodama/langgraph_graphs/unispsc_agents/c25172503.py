# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172503 — Tire Procurement (segment 25).

Bespoke logic for orchestrating tire acquisition workflows, including
specification validation, vendor selection simulation, and PO generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172503"
UNISPSC_TITLE = "Tire Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Tire Procurement
    specs_validated: bool
    inventory_confirmed: bool
    procurement_priority: str
    vendor_selection: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Checks the input for required tire dimensions and load ratings."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})
    # Simple check for required fields like size or tread type
    is_valid = bool(specs.get("size") and specs.get("rating"))
    priority = inp.get("priority", "standard")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "specs_validated": is_valid,
        "procurement_priority": priority,
    }


def check_vendor_availability(state: State) -> dict[str, Any]:
    """Simulates checking stock across registered tire vendors."""
    if not state.get("specs_validated"):
        return {
            "log": [f"{UNISPSC_CODE}:check_vendor_availability:skip"],
            "inventory_confirmed": False
        }

    # Mock logic: assume availability for standard requests
    return {
        "log": [f"{UNISPSC_CODE}:check_vendor_availability"],
        "inventory_confirmed": True,
        "vendor_selection": "GlobalTire-Wholesale-Alpha"
    }


def finalize_procurement_state(state: State) -> dict[str, Any]:
    """Prepares the final result and internal tracking tokens."""
    confirmed = state.get("inventory_confirmed", False)
    vendor = state.get("vendor_selection", "None")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if confirmed else "REJECTED",
            "selected_vendor": vendor,
            "ok": confirmed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("check_vendor_availability", check_vendor_availability)
_g.add_node("finalize_procurement_state", finalize_procurement_state)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "check_vendor_availability")
_g.add_edge("check_vendor_availability", "finalize_procurement_state")
_g.add_edge("finalize_procurement_state", END)

graph = _g.compile()
