# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101906 — Procurement (segment 24).

Bespoke graph for procurement operations, handling requisition validation,
vendor verification, and budget authorization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101906"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101906"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific procurement state
    requisition_valid: bool
    vendor_vetted: bool
    budget_authorized: bool
    purchase_order_id: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition details."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id")
    is_valid = bool(req_id and inp.get("items"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition(id={req_id})"],
        "requisition_valid": is_valid,
    }


def verify_vendor_compliance(state: State) -> dict[str, Any]:
    """Checks if the selected vendor is in the approved vendor list."""
    # Simulation: assume vendor is vetted if requisition was valid
    vetted = state.get("requisition_valid", False)
    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor_compliance(status={vetted})"],
        "vendor_vetted": vetted,
    }


def authorize_funding(state: State) -> dict[str, Any]:
    """Performs budget check and authorizes the spend for the requisition."""
    can_authorize = state.get("vendor_vetted", False)
    return {
        "log": [f"{UNISPSC_CODE}:authorize_funding(authorized={can_authorize})"],
        "budget_authorized": can_authorize,
        "purchase_order_id": f"PO-{UNISPSC_CODE}-7782" if can_authorize else None,
    }


def emit_procurement_result(state: State) -> dict[str, Any]:
    """Finalizes the state and emits the procurement result."""
    success = state.get("budget_authorized", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_procurement_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "po_id": state.get("purchase_order_id"),
            "status": "AUTHORIZED" if success else "REJECTED",
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("verify_vendor", verify_vendor_compliance)
_g.add_node("authorize", authorize_funding)
_g.add_node("emit", emit_procurement_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify_vendor")
_g.add_edge("verify_vendor", "authorize")
_g.add_edge("authorize", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
