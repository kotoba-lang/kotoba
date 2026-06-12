# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241600 — Procure (segment 23).
Bespoke implementation for industrial procurement workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241600"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Procurement
    requisition_id: str
    vendor_selection: str
    budget_clearance: bool
    po_reference: str
    workflow_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Verify the procurement request has the necessary metadata and budget clearance."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", f"REQ-{UNISPSC_CODE}-DEFAULT")
    estimated_cost = inp.get("estimated_cost", 0)

    # Simple logic: approve if cost is under a specific limit for this agent
    approved = estimated_cost < 500000

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition:{req_id}:approved={approved}"],
        "requisition_id": req_id,
        "budget_clearance": approved,
        "workflow_status": "validated" if approved else "failed_validation"
    }


def source_industrial_vendor(state: State) -> dict[str, Any]:
    """Select a vendor based on the industrial manufacturing segment requirements."""
    if state.get("workflow_status") == "failed_validation":
        return {"log": [f"{UNISPSC_CODE}:source_vendor:skipped"]}

    # In a real scenario, this might check a list of approved vendors for Segment 23
    selected_vendor = "VND-23-METAL-TECH"
    return {
        "log": [f"{UNISPSC_CODE}:source_vendor:{selected_vendor}"],
        "vendor_selection": selected_vendor,
        "workflow_status": "vendor_assigned"
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Finalize the procurement by generating a Purchase Order reference."""
    status = state.get("workflow_status")
    po_ref = "N/A"
    success = False

    if status == "vendor_assigned" and state.get("budget_clearance"):
        po_ref = f"PO-{state.get('requisition_id')}-FINAL"
        success = True

    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement:po={po_ref}"],
        "po_reference": po_ref,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purchase_order": po_ref,
            "success": success
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("source", source_industrial_vendor)
_g.add_node("execute", execute_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "source")
_g.add_edge("source", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
