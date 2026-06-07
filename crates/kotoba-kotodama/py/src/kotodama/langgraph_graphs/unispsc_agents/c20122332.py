# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122332 — Procure (segment 20).

Bespoke graph logic for the procurement of mining and well drilling machinery.
This agent handles requisition validation, inventory assessment, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122332"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122332"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for procurement operations
    requisition_valid: bool
    inventory_available: bool
    procurement_stage: str
    purchase_order_id: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition for mining equipment."""
    inp = state.get("input") or {}
    # A valid requisition requires an ID and a target item code
    is_valid = "requisition_id" in inp and "item_id" in inp
    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_valid": is_valid,
        "procurement_stage": "validated" if is_valid else "failed_validation",
    }


def check_inventory(state: State) -> dict[str, Any]:
    """Checks inventory availability for the requested machinery items."""
    inp = state.get("input") or {}
    item_id = str(inp.get("item_id", ""))
    # Mock logic: items prefixed with 'STOCK' are considered available
    available = item_id.startswith("STOCK")

    return {
        "log": [f"{UNISPSC_CODE}:check_inventory"],
        "inventory_available": available,
        "procurement_stage": "inventory_checked",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement cycle and emits the outcome."""
    valid = state.get("requisition_valid", False)
    available = state.get("inventory_available", False)

    po_id = ""
    status = "aborted"
    success = False

    if valid and available:
        po_id = f"PO-{UNISPSC_CODE}-TX"
        status = "completed"
        success = True

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "purchase_order_id": po_id,
        "procurement_stage": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": success,
            "po_id": po_id,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requisition)
_g.add_node("check_inventory", check_inventory)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "check_inventory")
_g.add_edge("check_inventory", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
