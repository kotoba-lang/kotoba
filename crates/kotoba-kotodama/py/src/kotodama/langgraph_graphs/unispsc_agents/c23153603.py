# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153603 — Robot Procurement (segment 23).

Bespoke logic for robot procurement workflows, handling requirement validation,
vendor evaluation, and purchase order issuance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153603"
UNISPSC_TITLE = "Robot Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Robot Procurement
    requirements_validated: bool
    vendor_tier: str
    delivery_estimate_days: int
    procurement_id: str


def verify_requirements(state: State) -> dict[str, Any]:
    """Validates the technical specifications for the requested robotic systems."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})
    # Simulation: ensure specifications are provided
    is_valid = len(specs) > 0
    return {
        "log": [f"{UNISPSC_CODE}:verify_requirements: valid={is_valid}"],
        "requirements_validated": is_valid,
        "procurement_id": inp.get("request_id", "REQ-AUTOGEN-001"),
    }


def evaluate_vendors(state: State) -> dict[str, Any]:
    """Evaluates available robotic hardware vendors based on validated requirements."""
    # Simulation: choose a tier based on validation status
    tier = "STRATEGIC" if state.get("requirements_validated") else "QUALIFIED"
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_vendors: tier={tier}"],
        "vendor_tier": tier,
    }


def issue_purchase_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement process and issues a procurement result."""
    tier = state.get("vendor_tier", "QUALIFIED")
    # Simulation: strategic vendors have shorter lead times
    days = 14 if tier == "STRATEGIC" else 45

    return {
        "log": [f"{UNISPSC_CODE}:issue_purchase_order"],
        "delivery_estimate_days": days,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": state.get("procurement_id"),
            "status": "PO_ISSUED",
            "vendor_tier": tier,
            "delivery_window_days": days,
            "ok": state.get("requirements_validated", False),
        },
    }


_g = StateGraph(State)

_g.add_node("verify_requirements", verify_requirements)
_g.add_node("evaluate_vendors", evaluate_vendors)
_g.add_node("issue_purchase_order", issue_purchase_order)

_g.add_edge(START, "verify_requirements")
_g.add_edge("verify_requirements", "evaluate_vendors")
_g.add_edge("evaluate_vendors", "issue_purchase_order")
_g.add_edge("issue_purchase_order", END)

graph = _g.compile()
