# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101503 — Procurement (segment 21).

Bespoke graph logic for handling procurement workflows, including requisition
validation, compliance auditing against budget constraints, and purchase order
generation. This agent ensures all procurement actions are logged and verified.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101503"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Procurement
    requisition_id: str
    is_budget_approved: bool
    compliance_check_passed: bool
    vendor_verification_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request and extracts identifiers."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-UNKNOWN")
    amount = inp.get("total_amount", 0.0)

    # Simple validation: requisitions must have an ID and a non-zero amount
    is_valid = req_id != "REQ-UNKNOWN" and amount > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "compliance_check_passed": is_valid
    }


def check_budget_and_vendor(state: State) -> dict[str, Any]:
    """Simulates checking the requisition against budget and vendor authorization."""
    inp = state.get("input") or {}
    amount = inp.get("total_amount", 0.0)

    # Threshold for automatic budget approval
    budget_ok = amount < 50000.0
    vendor_status = "AUTHORIZED" if "vendor_id" in inp else "UNVERIFIED"

    return {
        "log": [f"{UNISPSC_CODE}:check_budget_and_vendor"],
        "is_budget_approved": budget_ok,
        "vendor_verification_status": vendor_status
    }


def finalize_procurement_action(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and emits the structured result."""
    compliance_ok = state.get("compliance_check_passed", False)
    budget_ok = state.get("is_budget_approved", False)
    vendor_ok = state.get("vendor_verification_status") == "AUTHORIZED"

    overall_success = compliance_ok and budget_ok and vendor_ok

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_action"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": state.get("requisition_id"),
            "status": "APPROVED" if overall_success else "PENDING_REVIEW",
            "ok": overall_success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("audit", check_budget_and_vendor)
_g.add_node("finalize", finalize_procurement_action)

_g.add_edge(START, "validate")
_g.add_edge("validate", "audit")
_g.add_edge("audit", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
