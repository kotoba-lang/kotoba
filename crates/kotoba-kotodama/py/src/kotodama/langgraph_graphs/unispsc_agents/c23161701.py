# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23161701 — Robot Procurement (segment 23).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23161701"
UNISPSC_TITLE = "Robot Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23161701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Robot Procurement
    specifications_validated: bool
    selected_vendor: str
    budget_allocation: float
    procurement_reference: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates robotic payload, DOF, and precision requirements."""
    inp = state.get("input") or {}
    # Simulate validation of robotic specifications
    has_payload = "payload_kg" in inp
    has_dof = "dof" in inp
    is_valid = has_payload and has_dof
    ref_id = inp.get("ref_id", "REQ-AUTO-2316")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications:valid={is_valid}"],
        "specifications_validated": is_valid,
        "procurement_reference": ref_id,
    }


def assess_vendors(state: State) -> dict[str, Any]:
    """Matches requirements against a simulated robotics vendor database."""
    # Simulate vendor selection based on validation status
    if state.get("specifications_validated"):
        vendor = "Industrial Robotics Corp"
        budget = 245000.0
    else:
        vendor = "Unassigned"
        budget = 0.0

    return {
        "log": [f"{UNISPSC_CODE}:assess_vendors:selected={vendor}"],
        "selected_vendor": vendor,
        "budget_allocation": budget,
    }


def issue_procurement_order(state: State) -> dict[str, Any]:
    """Generates the final procurement record and status."""
    vendor = state.get("selected_vendor")
    is_ready = vendor != "Unassigned" and state.get("specifications_validated")

    return {
        "log": [f"{UNISPSC_CODE}:issue_procurement_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_id": f"PO-{state.get('procurement_reference')}",
            "vendor": vendor,
            "amount": state.get("budget_allocation"),
            "status": "ISSUED" if is_ready else "PENDING_SPECIFICATION",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("assess", assess_vendors)
_g.add_node("issue", issue_procurement_order)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "issue")
_g.add_edge("issue", END)

graph = _g.compile()
