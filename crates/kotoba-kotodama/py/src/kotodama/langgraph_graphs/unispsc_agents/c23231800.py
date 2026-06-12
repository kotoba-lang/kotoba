# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231800 — Procure (segment 23).

Bespoke graph logic for industrial procurement processes within segment 23.
This agent handles the validation of procurement requisitions, supplier
sourcing logic, and finalization of procurement records.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231800"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231800"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for "Procure"
    requisition_id: str
    budget_verified: bool
    supplier_selected: str
    procurement_status: str
    delivery_estimate_days: int


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request and checks budget constraints."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-000")
    # Simulate a budget check logic
    budget_ok = inp.get("amount", 0) < 1000000

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "budget_verified": budget_ok,
        "procurement_status": "validated" if budget_ok else "budget_rejected",
    }


def source_supplier(state: State) -> dict[str, Any]:
    """Identifies and selects a supplier based on the requisition details."""
    if not state.get("budget_verified"):
        return {"log": [f"{UNISPSC_CODE}:source_supplier_skipped"]}

    # Pure-Python selection logic
    supplier = "Industrial-Supply-Corp"
    return {
        "log": [f"{UNISPSC_CODE}:source_supplier"],
        "supplier_selected": supplier,
        "delivery_estimate_days": 14,
        "procurement_status": "supplier_assigned",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Wraps up the procurement process and emits the final status."""
    status = state.get("procurement_status", "unknown")
    ok = state.get("budget_verified", False) and "supplier_selected" in state

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": state.get("requisition_id"),
            "supplier": state.get("supplier_selected", "N/A"),
            "status": status,
            "ok": ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("source", source_supplier)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "source")
_g.add_edge("source", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
