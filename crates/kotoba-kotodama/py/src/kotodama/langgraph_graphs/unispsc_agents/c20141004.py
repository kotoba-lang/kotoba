# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141004 — Procurement (segment 20).

This bespoke agent handles procurement workflows, including requisition
verification, budget allocation, and purchase order fulfillment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141004"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for Procurement
    requisition_valid: bool
    budget_allocated: bool
    vendor_id: str
    purchase_order_id: str


def verify_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition details."""
    inp = state.get("input") or {}
    item = inp.get("item")
    quantity = inp.get("quantity", 0)

    is_valid = bool(item and quantity > 0)
    return {
        "log": [f"{UNISPSC_CODE}:verify_requisition(valid={is_valid})"],
        "requisition_valid": is_valid,
        "vendor_id": inp.get("vendor_id", "VENDOR-UNASSIGNED")
    }


def allocate_budget(state: State) -> dict[str, Any]:
    """Simulates internal budget check and allocation for the procurement."""
    valid = state.get("requisition_valid", False)
    # Simple logic: only allocate if requisition is valid
    success = valid
    return {
        "log": [f"{UNISPSC_CODE}:allocate_budget(success={success})"],
        "budget_allocated": success
    }


def fulfill_procurement(state: State) -> dict[str, Any]:
    """Issues the final purchase order and prepares the result state."""
    allocated = state.get("budget_allocated", False)
    po_id = f"PO-{UNISPSC_CODE}-778899" if allocated else "NONE"

    return {
        "log": [f"{UNISPSC_CODE}:fulfill_procurement(po_id={po_id})"],
        "purchase_order_id": po_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purchase_order_id": po_id,
            "status": "APPROVED" if allocated else "DENIED",
            "ok": allocated,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_requisition", verify_requisition)
_g.add_node("allocate_budget", allocate_budget)
_g.add_node("fulfill_procurement", fulfill_procurement)

_g.add_edge(START, "verify_requisition")
_g.add_edge("verify_requisition", "allocate_budget")
_g.add_edge("allocate_budget", "fulfill_procurement")
_g.add_edge("fulfill_procurement", END)

graph = _g.compile()
