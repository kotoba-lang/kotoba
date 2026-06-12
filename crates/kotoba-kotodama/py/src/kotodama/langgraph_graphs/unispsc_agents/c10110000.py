# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10110000 — Procurement (segment 10).
Bespoke logic for handling procurement requisitions and vendor verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10110000"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10110000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Procurement
    requisition_id: str
    vendor_verified: bool
    budget_approved: bool
    compliance_status: str


def validate_procurement_request(state: State) -> dict[str, Any]:
    """Validates the incoming requisition data and assigns a tracking ID."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-PRO-DEFAULT")
    items_count = len(inp.get("items", []))

    return {
        "log": [f"{UNISPSC_CODE}:validate_procurement_request"],
        "requisition_id": req_id,
        "compliance_status": "PENDING_VERIFICATION" if items_count > 0 else "INVALID_REQUEST",
    }


def verify_vendor_and_budget(state: State) -> dict[str, Any]:
    """Simulates checking vendor registration and internal budget availability."""
    req_id = state.get("requisition_id", "UNKNOWN")
    # Pure logic: assume verification passes if we have a non-default ID
    is_valid_id = req_id != "REQ-PRO-DEFAULT"

    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor_and_budget"],
        "vendor_verified": is_valid_id,
        "budget_approved": is_valid_id,
        "compliance_status": "VERIFIED" if is_valid_id else "FAILED_VERIFICATION",
    }


def process_purchase_authorization(state: State) -> dict[str, Any]:
    """Finalizes the procurement workflow and generates a result summary."""
    approved = state.get("budget_approved", False) and state.get("vendor_verified", False)
    req_id = state.get("requisition_id")

    return {
        "log": [f"{UNISPSC_CODE}:process_purchase_authorization"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": req_id,
            "authorized": approved,
            "po_reference": f"PO-{req_id}" if approved else None,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_procurement_request)
_g.add_node("verify", verify_vendor_and_budget)
_g.add_node("authorize", process_purchase_authorization)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
