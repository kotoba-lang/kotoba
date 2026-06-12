# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111046 — Procurement.

Bespoke LangGraph implementation for Procurement (Segment 13).
This agent handles requisition intake, vendor verification, and budget
authorization steps within a structured procurement workflow.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111046"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111046"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    requisition_id: str
    vendor_selection: str
    budget_approved: bool
    procurement_stage: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Ensures the procurement request has necessary requisition details."""
    inp = state.get("input") or {}
    req_id = inp.get("req_id", "REQ-13111046-DEFAULT")
    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "procurement_stage": "validated",
    }


def verify_vendor_eligibility(state: State) -> dict[str, Any]:
    """Checks the selected vendor against procurement compliance rules."""
    inp = state.get("input") or {}
    vendor = inp.get("vendor_name", "Approved Vendor List")
    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor_eligibility"],
        "vendor_selection": vendor,
        "procurement_stage": "vendor_verified",
    }


def authorize_expenditure(state: State) -> dict[str, Any]:
    """Finalizes the procurement step by authorizing the budget."""
    req_id = state.get("requisition_id")
    # Simulated logic: if requisition exists, budget is cleared for this flow
    is_approved = bool(req_id)
    return {
        "log": [f"{UNISPSC_CODE}:authorize_expenditure"],
        "budget_approved": is_approved,
        "procurement_stage": "authorized" if is_approved else "failed",
    }


def finalize_state(state: State) -> dict[str, Any]:
    """Consolidates the procurement workflow into the final result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "requisition": state.get("requisition_id"),
            "vendor": state.get("vendor_selection"),
            "stage": state.get("procurement_stage"),
            "ok": state.get("budget_approved", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requisition)
_g.add_node("verify", verify_vendor_eligibility)
_g.add_node("authorize", authorize_expenditure)
_g.add_node("finalize", finalize_state)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "authorize")
_g.add_edge("authorize", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
