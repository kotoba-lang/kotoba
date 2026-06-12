# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101729 — Procure (segment 26).

Bespoke graph logic for the procurement lifecycle within segment 26
(Power Generation and Distribution Machinery and Accessories).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101729"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101729"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific procurement state fields
    requisition_id: str
    budget_code: str
    vendor_authorized: bool
    procurement_status: str


def check_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition and associated budget."""
    inp = state.get("input") or {}
    req_id = inp.get("id", "REQ-PENDING")
    b_code = inp.get("budget", "NONE")

    # Simple validation: require a budget code to proceed
    is_valid = b_code != "NONE"

    return {
        "log": [f"{UNISPSC_CODE}:check_requisition"],
        "requisition_id": req_id,
        "budget_code": b_code,
        "procurement_status": "VALIDATED" if is_valid else "REJECTED"
    }


def authorize_vendor(state: State) -> dict[str, Any]:
    """Checks the authorization status of the selected vendor for segment 26."""
    status = state.get("procurement_status")
    authorized = False

    if status == "VALIDATED":
        # Simulate lookup in an approved vendor database
        authorized = True

    return {
        "log": [f"{UNISPSC_CODE}:authorize_vendor"],
        "vendor_authorized": authorized,
        "procurement_status": "AUTHORIZED" if authorized else "VENDOR_UNAUTHORIZED"
    }


def issue_purchase_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement process by issuing a mock purchase order."""
    is_auth = state.get("vendor_authorized", False)
    req_id = state.get("requisition_id", "N/A")
    status = state.get("procurement_status")

    success = is_auth and status == "AUTHORIZED"

    return {
        "log": [f"{UNISPSC_CODE}:issue_purchase_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "requisition_id": req_id,
            "status": "PO_ISSUED" if success else "PROCUREMENT_FAILED",
            "did": UNISPSC_DID,
            "success": success,
            "segment_lock": UNISPSC_SEGMENT
        }
    }


_g = StateGraph(State)

_g.add_node("check", check_requisition)
_g.add_node("authorize", authorize_vendor)
_g.add_node("finalize", issue_purchase_order)

_g.add_edge(START, "check")
_g.add_edge("check", "authorize")
_g.add_edge("authorize", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
