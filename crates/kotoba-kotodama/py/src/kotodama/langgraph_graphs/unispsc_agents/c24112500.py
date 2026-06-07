# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112500 — Supply (segment 24).

Bespoke graph for supply chain management within the segment 24 (Material Handling
and Conditioning and Storage Equipment and Supplies). This agent manages the
lifecycle of supply requisitions from validation through inventory allocation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112500"
UNISPSC_TITLE = "Supply"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Supply
    requisition_id: str
    inventory_status: str
    allocation_confirmed: bool
    supply_category: str
    priority_level: int


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming supply requisition and extracts metadata."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-GEN-001")
    category = inp.get("category", "general_handling_supplies")
    priority = inp.get("priority", 1)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition -> {req_id}"],
        "requisition_id": req_id,
        "supply_category": category,
        "priority_level": priority,
        "inventory_status": "pending_check"
    }


def allocate_resources(state: State) -> dict[str, Any]:
    """Simulates the allocation of inventory resources for the supply request."""
    category = state.get("supply_category", "unknown")
    priority = state.get("priority_level", 1)

    # Logic: High priority or recognized categories get immediate allocation
    is_allocatable = priority > 0 and category != "unknown"

    return {
        "log": [f"{UNISPSC_CODE}:allocate_resources for {category} (Priority {priority})"],
        "allocation_confirmed": is_allocatable,
        "inventory_status": "allocated" if is_allocatable else "out_of_stock"
    }


def finalize_supply_order(state: State) -> dict[str, Any]:
    """Finalizes the supply transaction and prepares the actor's response."""
    success = state.get("allocation_confirmed", False)
    req_id = state.get("requisition_id", "N/A")
    status = state.get("inventory_status", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_supply_order -> {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": req_id,
            "transaction_status": "completed" if success else "rejected",
            "inventory_status": status,
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_requisition", validate_requisition)
_g.add_node("allocate_resources", allocate_resources)
_g.add_node("finalize_supply_order", finalize_supply_order)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "allocate_resources")
_g.add_edge("allocate_resources", "finalize_supply_order")
_g.add_edge("finalize_supply_order", END)

graph = _g.compile()
