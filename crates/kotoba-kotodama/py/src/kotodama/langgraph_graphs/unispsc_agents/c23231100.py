# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231100 — Procure (segment 23).

This module implements a bespoke procurement workflow for industrial manufacturing services.
It handles requisition validation, vendor selection simulation, and funding authorization
using a state-based graph execution model.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231100"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Procurement
    requisition_id: str
    vendor_id: str
    budget_limit: float
    funding_authorized: bool
    procurement_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request and initializes tracking."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-GEN-001")
    limit = float(inp.get("amount", 1000.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition:{req_id}"],
        "requisition_id": req_id,
        "budget_limit": limit,
        "procurement_status": "VALIDATED",
    }


def source_vendor(state: State) -> dict[str, Any]:
    """Simulates vendor selection based on requisition details."""
    req_id = state.get("requisition_id", "UNKNOWN")
    # Logic to 'select' a vendor from a simulated directory
    v_id = f"VEND-{req_id.split('-')[-1]}"

    return {
        "log": [f"{UNISPSC_CODE}:source_vendor:{v_id}"],
        "vendor_id": v_id,
        "procurement_status": "VENDOR_ASSIGNED",
    }


def authorize_funds(state: State) -> dict[str, Any]:
    """Checks the budget limit and authorizes the procurement transaction."""
    limit = state.get("budget_limit", 0.0)
    # Simple business logic: auto-authorize if under 5000 units
    authorized = limit < 5000.0
    status = "AUTHORIZED" if authorized else "PENDING_MANUAL_REVIEW"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_funds:{status}"],
        "funding_authorized": authorized,
        "procurement_status": status,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Compiles the final procurement result for the caller."""
    authorized = state.get("funding_authorized", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": state.get("requisition_id"),
            "vendor_id": state.get("vendor_id"),
            "status": state.get("procurement_status"),
            "authorized": authorized,
            "ok": authorized,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("source", source_vendor)
_g.add_node("authorize", authorize_funds)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "source")
_g.add_edge("source", "authorize")
_g.add_edge("authorize", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
