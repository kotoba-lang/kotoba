# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172408 — Procure (segment 25).

Bespoke graph for procurement operations within the vehicle components segment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172408"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172408"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for "Procure"
    requisition_id: str
    vendor_id: str
    budget_approved: bool
    inventory_available: bool
    procurement_method: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition and metadata."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-25172408-001")
    amount = inp.get("amount", 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "budget_approved": amount < 50000,
        "procurement_method": "direct" if amount < 5000 else "competitive_bid"
    }


def verify_vendor_source(state: State) -> dict[str, Any]:
    """Selects and verifies the vendor based on procurement method."""
    method = state.get("procurement_method", "direct")
    vendor = "PRE-APPROVED-V01" if method == "direct" else "BID-PENDING"

    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor_source"],
        "vendor_id": vendor,
        "inventory_available": True
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and prepares the output."""
    approved = state.get("budget_approved", False)
    status = "READY_FOR_PO" if approved else "BUDGET_REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": state.get("requisition_id"),
            "vendor_id": state.get("vendor_id"),
            "status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requisition)
_g.add_node("verify", verify_vendor_source)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
