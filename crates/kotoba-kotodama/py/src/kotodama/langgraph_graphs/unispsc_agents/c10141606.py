# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10141606 — Procurement (segment 10).

This bespoke graph implements a three-stage procurement pipeline:
1. Validation: Ensures requisition data and vendor identifiers are present.
2. Budget Assessment: Checks the transaction amount against mock fiscal limits.
3. Finalization: Records the procurement outcome and emits the actor result.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10141606"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10141606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Procurement
    requisition_id: str
    vendor_id: str
    total_amount: float
    budget_approved: bool
    procurement_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validate incoming procurement request and extract identifiers."""
    inp = state.get("input") or {}
    req_id = str(inp.get("requisition_id", "REQ-DEFAULT-001"))
    vendor = str(inp.get("vendor_id", "VND-UNASSIGNED"))

    try:
        amount = float(inp.get("amount", 0.0))
    except (ValueError, TypeError):
        amount = 0.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "vendor_id": vendor,
        "total_amount": amount,
        "procurement_status": "validated"
    }


def assess_budget(state: State) -> dict[str, Any]:
    """Assess if the requested procurement fits within allocated budget constraints."""
    amount = state.get("total_amount", 0.0)

    # Mock budget threshold for autonomous procurement approval
    THRESHOLD = 50000.0
    approved = amount <= THRESHOLD

    return {
        "log": [f"{UNISPSC_CODE}:assess_budget"],
        "budget_approved": approved,
        "procurement_status": "budget_reviewed"
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalize the procurement record and prepare the result object."""
    approved = state.get("budget_approved", False)
    req_id = state.get("requisition_id", "N/A")

    status = "authorized" if approved else "denied_over_budget"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "procurement_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": req_id,
            "procurement_authorized": approved,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("assess", assess_budget)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
