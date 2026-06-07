# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111608 — Paper Procurement (segment 14).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111608"
UNISPSC_TITLE = "Paper Procurement"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111608"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    paper_specification: str
    order_quantity: int
    supplier_status: str
    inventory_available: bool


def assess_requirement(state: State) -> dict[str, Any]:
    """Evaluates the input to extract paper procurement details."""
    inp = state.get("input") or {}
    spec = inp.get("specification", "Standard A4, 80gsm")
    qty = inp.get("quantity", 500)
    return {
        "log": [f"{UNISPSC_CODE}:assess_requirement"],
        "paper_specification": spec,
        "order_quantity": qty,
    }


def verify_inventory(state: State) -> dict[str, Any]:
    """Simulates checking regional inventory for the requested paper stock."""
    spec = state.get("paper_specification", "Unknown")
    qty = state.get("order_quantity", 0)
    # Simulate an inventory check logic
    is_available = qty < 5000
    return {
        "log": [f"{UNISPSC_CODE}:verify_inventory:{spec}"],
        "inventory_available": is_available,
        "supplier_status": "Pre-qualified" if is_available else "Out-of-Stock",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and prepares the output result."""
    available = state.get("inventory_available", False)
    status_label = "Confirmed" if available else "Rejected-Shortage"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": state.get("paper_specification"),
            "quantity": state.get("order_quantity"),
            "procurement_status": status_label,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("assess_requirement", assess_requirement)
_g.add_node("verify_inventory", verify_inventory)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "assess_requirement")
_g.add_edge("assess_requirement", "verify_inventory")
_g.add_edge("verify_inventory", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
