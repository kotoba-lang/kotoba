# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111803 — Paper Procurement (segment 14).

This agent manages the lifecycle of paper procurement, ensuring that
specifications (GSM weight, brightness, and recycled content) meet
sustainability and quality standards before finalizing the requisition.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111803"
UNISPSC_TITLE = "Paper Procurement"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Paper Procurement
    specification_verified: bool
    recycled_content_pct: float
    gsm_weight: int
    inventory_available: bool
    procurement_id: str


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the technical specifications of the paper requested."""
    inp = state.get("input") or {}
    # Simulate extraction or validation of paper specs
    gsm = inp.get("gsm", 80)
    recycled = inp.get("recycled_pct", 30.0)

    # Paper procurement policy: Must be at least 20% recycled content
    is_valid = recycled >= 20.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "gsm_weight": gsm,
        "recycled_content_pct": recycled,
        "specification_verified": is_valid,
    }


def check_supplier_inventory(state: State) -> dict[str, Any]:
    """Checks real-time availability for the specified paper grade."""
    # Logic based on previous node's validation
    if not state.get("specification_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:check_supplier_inventory:skipped_due_to_spec_failure"],
            "inventory_available": False
        }

    # Simulate a successful inventory lookup
    return {
        "log": [f"{UNISPSC_CODE}:check_supplier_inventory:available"],
        "inventory_available": True,
        "procurement_id": f"REQ-{UNISPSC_CODE}-7782"
    }


def finalize_requisition(state: State) -> dict[str, Any]:
    """Generates the final procurement result and audit log."""
    spec_ok = state.get("specification_verified", False)
    inv_ok = state.get("inventory_available", False)
    success = spec_ok and inv_ok

    return {
        "log": [f"{UNISPSC_CODE}:finalize_requisition"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "procurement_id": state.get("procurement_id"),
            "status": "approved" if success else "rejected",
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specification", validate_specification)
_g.add_node("check_supplier_inventory", check_supplier_inventory)
_g.add_node("finalize_requisition", finalize_requisition)

_g.add_edge(START, "validate_specification")
_g.add_edge("validate_specification", "check_supplier_inventory")
_g.add_edge("check_supplier_inventory", "finalize_requisition")
_g.add_edge("finalize_requisition", END)

graph = _g.compile()
