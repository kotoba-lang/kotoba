# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142100 — Procurement (segment 20).

Bespoke implementation for procurement workflows, including requisition
validation, fund authorization, and purchase order generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142100"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Procurement
    requisition_id: str
    vendor_vetted: bool
    budget_approved: bool
    purchase_order_id: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request and identifies the requisition."""
    inp = state.get("input") or {}
    req_id = inp.get("req_id", "REQ-000")
    is_vetted = inp.get("priority") != "emergency"

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "vendor_vetted": is_vetted,
    }


def authorize_funds(state: State) -> dict[str, Any]:
    """Checks budget availability and authorizes the procurement."""
    # Logic to simulate budget authorization
    return {
        "log": [f"{UNISPSC_CODE}:authorize_funds"],
        "budget_approved": True,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final purchase order and result payload."""
    po_id = f"PO-{state.get('requisition_id', '000')}-2026"
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "purchase_order_id": po_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "po_id": po_id,
            "status": "issued",
            "did": UNISPSC_DID,
            "ok": state.get("budget_approved", False),
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("authorize", authorize_funds)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "authorize")
_g.add_edge("authorize", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
