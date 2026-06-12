# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242600 — Procure (segment 23).

This agent handles the procurement lifecycle for industrial manufacturing
machinery and accessories, covering requisition validation, budget
clearance, and final issuance of purchase orders.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242600"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Procure
    requisition_id: str
    vendor_reference: str
    budget_cleared: bool
    order_confirmation: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the procurement request and vendor information."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-23242600-X")
    vref = inp.get("vendor_reference", "VND-PENDING")

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "vendor_reference": vref,
    }


def verify_funds(state: State) -> dict[str, Any]:
    """Verifies that funds are allocated for the procurement request."""
    # Deterministic simulation of budget verification
    req_id = state.get("requisition_id", "")
    is_cleared = bool(req_id and "REQ" in req_id)

    return {
        "log": [f"{UNISPSC_CODE}:verify_funds"],
        "budget_cleared": is_cleared,
    }


def issue_purchase_order(state: State) -> dict[str, Any]:
    """Issues the final purchase order and records the result."""
    cleared = state.get("budget_cleared", False)
    req_id = state.get("requisition_id", "UNKNOWN")
    vref = state.get("vendor_reference", "UNKNOWN")

    status = "ISSUED" if cleared else "REJECTED"
    conf = f"PO-{UNISPSC_CODE}-{req_id[-4:]}" if cleared else "NONE"

    return {
        "log": [f"{UNISPSC_CODE}:issue_purchase_order"],
        "order_confirmation": conf,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": req_id,
            "vendor": vref,
            "order_status": status,
            "confirmation": conf,
            "ok": cleared,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_requisition", validate_requisition)
_g.add_node("verify_funds", verify_funds)
_g.add_node("issue_purchase_order", issue_purchase_order)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "verify_funds")
_g.add_edge("verify_funds", "issue_purchase_order")
_g.add_edge("issue_purchase_order", END)

graph = _g.compile()
