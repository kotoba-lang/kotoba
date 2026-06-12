# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101707 — Procure (segment 26).

Bespoke logic for procurement workflows within the power generation sector.
Handles requisition validation, vendor selection, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101707"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101707"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for "Procure"
    requisition_id: str
    vendor_selection: list[str]
    total_cost: float
    approval_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request and extracts basic info."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-000")
    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "approval_status": "PENDING",
    }


def evaluate_vendors(state: State) -> dict[str, Any]:
    """Simulates vendor evaluation for the requested power machinery."""
    # Logic to select vendors based on input (placeholder logic)
    vendors = ["Vendor_Alpha", "Vendor_Beta"]
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_vendors"],
        "vendor_selection": vendors,
        "total_cost": 50000.0,
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement order and prepares the result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_order"],
        "approval_status": "APPROVED",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": state.get("requisition_id"),
            "status": "ORDER_PLACED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requisition)
_g.add_node("evaluate", evaluate_vendors)
_g.add_node("finalize", finalize_order)

_g.add_edge(START, "validate")
_g.add_edge("validate", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
