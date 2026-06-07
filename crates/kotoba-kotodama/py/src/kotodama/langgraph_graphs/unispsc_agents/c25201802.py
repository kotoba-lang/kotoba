# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201802 — Procure (segment 25).

Bespoke logic for vehicle and specialty trailer procurement within the
UNISPSC 25201802 domain. This agent validates requisition data, sources
compliant vendors, and finalizes procurement orders.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201802"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201802"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    requisition_id: str
    vendor_id: str
    budget_approved: bool
    spec_verification: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-25201802-DEFAULT")
    # Basic budget rule for specialty vehicles
    amount = inp.get("amount", 0)
    has_budget = amount > 0 and amount < 750000

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "budget_approved": has_budget,
    }


def source_vendor(state: State) -> dict[str, Any]:
    """Identifies a vendor capable of supplying the requested trailer."""
    req_id = state.get("requisition_id", "UNKNOWN")
    # Simulation of vendor lookup based on requisition ID
    vendor_id = f"VND-{req_id[-4:]}-SPECIALTY-TRAILERS"

    return {
        "log": [f"{UNISPSC_CODE}:source_vendor"],
        "vendor_id": vendor_id,
        "spec_verification": "SEGMENT_25_COMPLIANT",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and prepares the output result."""
    req_id = state.get("requisition_id")
    vendor_id = state.get("vendor_id")
    approved = state.get("budget_approved", False)
    spec_status = state.get("spec_verification")

    status = "PROCUREMENT_AUTHORIZED" if approved else "BUDGET_REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": status,
            "requisition_id": req_id,
            "vendor_id": vendor_id,
            "compliance": spec_status,
            "did": UNISPSC_DID,
            "ok": approved,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requisition)
_g.add_node("source", source_vendor)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "source")
_g.add_edge("source", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
