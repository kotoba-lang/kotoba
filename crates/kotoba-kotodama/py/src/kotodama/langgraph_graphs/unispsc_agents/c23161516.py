# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23161516 — Procurement (segment 23).

Bespoke logic for procurement workflow automation, handling requisition
validation, budget verification, and final execution steps.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23161516"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23161516"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific procurement state
    requisition_id: str
    vendor_id: str
    budget_cleared: bool
    approval_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validate incoming procurement requisition and identify key entities."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-DEFAULT-001")
    ven_id = inp.get("vendor_id", "VEN-NOT-SPECIFIED")

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "vendor_id": ven_id,
        "approval_status": "IDENTIFIED"
    }


def verify_budget(state: State) -> dict[str, Any]:
    """Simulate budget availability check for the procurement request."""
    req_id = state.get("requisition_id", "")
    # Simple logic: REQ-FAIL triggers a budget rejection
    is_cleared = "FAIL" not in req_id

    return {
        "log": [f"{UNISPSC_CODE}:verify_budget"],
        "budget_cleared": is_cleared,
        "approval_status": "APPROVED" if is_cleared else "REJECTED"
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Finalize the procurement process and prepare the response object."""
    success = state.get("budget_cleared", False)

    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition": state.get("requisition_id"),
            "vendor": state.get("vendor_id"),
            "final_status": state.get("approval_status"),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("verify", verify_budget)
_g.add_node("execute", execute_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
