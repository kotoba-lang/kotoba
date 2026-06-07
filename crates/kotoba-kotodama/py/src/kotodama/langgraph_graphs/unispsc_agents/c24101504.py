# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101504 — Procurement (segment 24).

Bespoke LangGraph implementation for Procurement services.
This agent manages the requisition-to-purchase-order lifecycle, including
vendor selection validation and budget allocation verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101504"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Procurement
    requisition_id: str
    vendor_verified: bool
    budget_approved: bool
    purchase_order_id: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition and vendor data."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-TEMP-001")
    vendor_id = inp.get("vendor_id")

    # Simulate vendor verification logic
    vendor_ok = vendor_id is not None and vendor_id.startswith("VEN-")

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition:{req_id}"],
        "requisition_id": req_id,
        "vendor_verified": vendor_ok,
    }


def verify_budget(state: State) -> dict[str, Any]:
    """Checks if the requisition amount is within the departmental budget."""
    inp = state.get("input") or {}
    amount = inp.get("amount", 0)
    limit = inp.get("budget_limit", 10000)

    approved = amount <= limit

    return {
        "log": [f"{UNISPSC_CODE}:verify_budget:approved={approved}"],
        "budget_approved": approved,
    }


def generate_po(state: State) -> dict[str, Any]:
    """Generates a Purchase Order if all checks passed."""
    success = state.get("vendor_verified") and state.get("budget_approved")
    po_id = f"PO-{state.get('requisition_id', 'ERR')}" if success else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:generate_po:{po_id}"],
        "purchase_order_id": po_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purchase_order_id": po_id,
            "status": "ISSUED" if success else "FAILED",
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_requisition", validate_requisition)
_g.add_node("verify_budget", verify_budget)
_g.add_node("generate_po", generate_po)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "verify_budget")
_g.add_edge("verify_budget", "generate_po")
_g.add_edge("generate_po", END)

graph = _g.compile()
