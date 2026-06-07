# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172405 — Procure (segment 25).

Bespoke graph logic for vehicle-related procurement services. This agent
handles the transition from requisition review through budget verification
to final purchase order issuance for vehicle components and systems within
the transportation segment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172405"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172405"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Bespoke domain fields for vehicle procurement
    requisition_id: str
    budget_approved: bool
    procurement_stage: str
    inventory_confirmed: bool


def review_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request for vehicle parts."""
    inp = state.get("input") or {}
    req_id = inp.get("req_id", "REQ-V-25-001")
    part_id = inp.get("part_id", "CHASSIS-MOD-04")

    return {
        "log": [f"{UNISPSC_CODE}:review_requisition:part={part_id}"],
        "requisition_id": req_id,
        "procurement_stage": "reviewed",
    }


def verify_budget(state: State) -> dict[str, Any]:
    """Performs a mock check of departmental funds for the procurement."""
    # Logic: approve budget if requisition was successfully established
    has_req = bool(state.get("requisition_id"))

    return {
        "log": [f"{UNISPSC_CODE}:verify_budget:has_req={has_req}"],
        "budget_approved": has_req,
        "inventory_confirmed": True,
        "procurement_stage": "authorized" if has_req else "rejected",
    }


def issue_purchase_order(state: State) -> dict[str, Any]:
    """Generates the final procurement result and issues the PO."""
    success = state.get("budget_approved", False)
    req_id = state.get("requisition_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:issue_purchase_order:success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "PO_ISSUED" if success else "FAILED",
            "requisition_id": req_id,
            "ok": success,
        },
        "procurement_stage": "completed",
    }


_g = StateGraph(State)

_g.add_node("review", review_requisition)
_g.add_node("verify", verify_budget)
_g.add_node("issue", issue_purchase_order)

_g.add_edge(START, "review")
_g.add_edge("review", "verify")
_g.add_edge("verify", "issue")
_g.add_edge("issue", END)

graph = _g.compile()
