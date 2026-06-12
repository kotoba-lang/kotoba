# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15111702 — Procurement (segment 15).

Bespoke LangGraph logic for managing procurement workflows, including
requisition review, vendor sourcing, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15111702"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15111702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Procurement
    requisition_verified: bool
    vendor_sourced: bool
    budget_authorized: bool
    purchase_order_id: str


def review_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request and checks budget constraints."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-000")

    # Logic: Verify if input contains necessary procurement details
    is_valid = bool(inp.get("items") and inp.get("total_amount", 0) > 0)
    amount = inp.get("total_amount", 0)

    return {
        "log": [f"{UNISPSC_CODE}:review_requisition:{req_id}"],
        "requisition_verified": is_valid,
        "budget_authorized": is_valid and amount < 1000000,
    }


def source_vendor(state: State) -> dict[str, Any]:
    """Identifies and vets vendors for the requested items."""
    if not state.get("requisition_verified"):
        return {"log": [f"{UNISPSC_CODE}:source_vendor:skipped"]}

    return {
        "log": [f"{UNISPSC_CODE}:source_vendor:success"],
        "vendor_sourced": True,
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Generates the final purchase order and sets the result."""
    req_ok = state.get("requisition_verified")
    vendor_ok = state.get("vendor_sourced")
    budget_ok = state.get("budget_authorized")

    po_id = "PO-REJECTED"
    if req_ok and vendor_ok and budget_ok:
        po_id = f"PO-{UNISPSC_CODE}-12345"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_order:{po_id}"],
        "purchase_order_id": po_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "po_id": po_id,
            "status": "APPROVED" if po_id.startswith(f"PO-{UNISPSC_CODE[:4]}") else "REJECTED",
            "ok": po_id.startswith(f"PO-{UNISPSC_CODE}"),
        },
    }


_g = StateGraph(State)
_g.add_node("review_requisition", review_requisition)
_g.add_node("source_vendor", source_vendor)
_g.add_node("finalize_order", finalize_order)

_g.add_edge(START, "review_requisition")
_g.add_edge("review_requisition", "source_vendor")
_g.add_edge("source_vendor", "finalize_order")
_g.add_edge("finalize_order", END)

graph = _g.compile()
