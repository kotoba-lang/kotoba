# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231001 — Procure (segment 23).

Bespoke implementation for industrial procurement services, handling
requisition validation, budget authorization, and purchase order issuance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231001"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231001"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Procure
    requisition_id: str
    vendor_id: str
    budget_authorized: bool
    po_number: str
    procurement_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Ensures the procurement request contains necessary metadata."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-PENDING")
    vendor = inp.get("vendor_id", "VND-DEFAULT")

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "vendor_id": vendor,
        "procurement_status": "VALIDATED",
    }


def authorize_budget(state: State) -> dict[str, Any]:
    """Simulates financial authorization for the industrial service."""
    # Authorization is granted if a requisition ID exists
    has_req = state.get("requisition_id") != "REQ-PENDING"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_budget"],
        "budget_authorized": has_req,
        "procurement_status": "AUTHORIZED" if has_req else "DENIED",
    }


def issue_purchase_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement and issues a tracking number."""
    authorized = state.get("budget_authorized", False)
    req_id = state.get("requisition_id", "000")
    po_val = f"PO-{UNISPSC_CODE}-{req_id}" if authorized else "VOID"

    return {
        "log": [f"{UNISPSC_CODE}:issue_purchase_order"],
        "po_number": po_val,
        "procurement_status": "ISSUED" if authorized else "FAILED",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "po_number": po_val,
            "did": UNISPSC_DID,
            "ok": authorized,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_requisition", validate_requisition)
_g.add_node("authorize_budget", authorize_budget)
_g.add_node("issue_purchase_order", issue_purchase_order)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "authorize_budget")
_g.add_edge("authorize_budget", "issue_purchase_order")
_g.add_edge("issue_purchase_order", END)

graph = _g.compile()
