# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11151611 — Procure (segment 11).

Bespoke graph logic for the procurement of live plant and animal material.
This agent handles requisition validation, vendor compliance auditing,
and final procurement authorization for segment 11 commodities.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151611"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151611"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Procure (Segment 11)
    requisition_id: str
    vendor_compliance_score: int
    budget_allocation_code: str
    procurement_priority: str
    authorized_signatory: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition for live material."""
    inp = state.get("input") or {}
    req_id = inp.get("req_id", "REQ-11-DEFAULT")
    priority = inp.get("priority", "standard")

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "procurement_priority": priority,
    }


def audit_compliance(state: State) -> dict[str, Any]:
    """Audits vendor compliance for live material handling and logistics."""
    # Simulated compliance logic based on priority and input flags
    priority = state.get("procurement_priority")
    score = 92 if priority == "high" else 88

    return {
        "log": [f"{UNISPSC_CODE}:audit_compliance"],
        "vendor_compliance_score": score,
        "budget_allocation_code": f"ALLOC-{UNISPSC_SEGMENT}-2026",
    }


def authorize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement authorization and emits the result."""
    score = state.get("vendor_compliance_score", 0)
    # Threshold for live material procurement is strict
    is_approved = score >= 85

    signatory = "CHIEF_PROCUREMENT_OFFICER" if is_approved else "NONE"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_procurement"],
        "authorized_signatory": signatory,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "AUTHORIZED" if is_approved else "REJECTED",
            "requisition_id": state.get("requisition_id"),
            "compliance_rating": "PASS" if is_approved else "FAIL",
            "ok": is_approved,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_requisition", validate_requisition)
_g.add_node("audit_compliance", audit_compliance)
_g.add_node("authorize_procurement", authorize_procurement)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "audit_compliance")
_g.add_edge("audit_compliance", "authorize_procurement")
_g.add_edge("authorize_procurement", END)

graph = _g.compile()
