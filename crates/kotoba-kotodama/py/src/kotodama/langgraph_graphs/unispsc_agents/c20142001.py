# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142001 — Proc.
Mining and Oil and Gas Services (segment 20).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142001"
UNISPSC_TITLE = "Proc"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142001"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Procurement/Processing in Oil & Gas
    requisition_id: str
    supplier_verified: bool
    safety_compliance_score: float
    order_status: str


def validate_proc_request(state: State) -> dict[str, Any]:
    """Validates the procurement requisition and safety requirements."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-TEMP-001")
    # Simulate safety check for segment 20 operations
    safety_score = 0.95 if inp.get("safety_certified") else 0.70

    return {
        "log": [f"{UNISPSC_CODE}:validate_proc_request"],
        "requisition_id": req_id,
        "safety_compliance_score": safety_score,
        "supplier_verified": False,
    }


def execute_sourcing(state: State) -> dict[str, Any]:
    """Handles supplier verification and order placement logic."""
    # Logic for mining/oil/gas service procurement
    is_safe = state.get("safety_compliance_score", 0) > 0.8
    verified = True if is_safe else False

    return {
        "log": [f"{UNISPSC_CODE}:execute_sourcing"],
        "supplier_verified": verified,
        "order_status": "PLACED" if verified else "HELD_FOR_REVIEW",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final result and closes the transaction."""
    status = state.get("order_status", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "requisition_id": state.get("requisition_id"),
            "status": status,
            "safety_verified": state.get("supplier_verified"),
            "did": UNISPSC_DID,
            "ok": status == "PLACED",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_proc_request)
_g.add_node("source", execute_sourcing)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "source")
_g.add_edge("source", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
