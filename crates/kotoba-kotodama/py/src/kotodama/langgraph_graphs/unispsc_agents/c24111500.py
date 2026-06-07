# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111500 — Bag Procurement (segment 24).

Bespoke graph for bag procurement workflows, handling specification
validation, supplier availability verification, and final record emission.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111500"
UNISPSC_TITLE = "Bag Procurement"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Bag Procurement
    spec_validated: bool
    supplier_id: str
    quantity_available: int
    quote_accepted: bool


def validate_procurement_request(state: State) -> dict[str, Any]:
    """Verify the bag specifications and quantity in the input."""
    inp = state.get("input") or {}
    bag_type = inp.get("bag_type")
    quantity = inp.get("quantity", 0)
    is_valid = bool(bag_type and quantity > 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_procurement_request"],
        "spec_validated": is_valid,
        "quantity_available": quantity if is_valid else 0,
    }


def verify_supplier(state: State) -> dict[str, Any]:
    """Check supplier availability for the validated bag specification."""
    # Simulation: assume a default supplier if specifications were validated
    if state.get("spec_validated"):
        return {
            "log": [f"{UNISPSC_CODE}:verify_supplier"],
            "supplier_id": "SUPP-BAG-24-001",
            "quote_accepted": True,
        }
    return {
        "log": [f"{UNISPSC_CODE}:verify_supplier_failed"],
        "supplier_id": "",
        "quote_accepted": False,
    }


def emit_procurement_order(state: State) -> dict[str, Any]:
    """Finalize the procurement order and emit the result."""
    ok = state.get("spec_validated", False) and state.get("quote_accepted", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_procurement_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": ok,
            "order_details": {
                "supplier": state.get("supplier_id"),
                "quantity": state.get("quantity_available"),
                "status": "ORDER_PLACED" if ok else "ORDER_CANCELLED"
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_procurement_request)
_g.add_node("verify", verify_supplier)
_g.add_node("emit", emit_procurement_order)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
