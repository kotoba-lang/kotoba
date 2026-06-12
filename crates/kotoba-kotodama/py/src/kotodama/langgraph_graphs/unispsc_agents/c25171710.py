# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171710 — Procure.

This agent handles the procurement workflow for vehicle components and transportation
systems within segment 25. It orchestrates requisition analysis, supplier vetting,
budget allocation, and final order issuance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171710"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171710"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Procurement
    requisition_id: str
    part_specification: dict[str, Any]
    supplier_compliance_verified: bool
    budget_allocation_code: str
    procurement_phase: str


def analyze_requisition(state: State) -> dict[str, Any]:
    """Evaluates the incoming procurement request for automotive or vehicle parts."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-25-DEFAULT")
    specs = inp.get("specifications", {"standard": "ISO-9001"})

    return {
        "log": [f"{UNISPSC_CODE}:analyze_requisition:{req_id}"],
        "requisition_id": req_id,
        "part_specification": specs,
        "procurement_phase": "ANALYZED",
    }


def vet_supplier(state: State) -> dict[str, Any]:
    """Verifies that the chosen supplier meets segment-specific regulatory requirements."""
    # In a real scenario, this might lookup a registry of approved vehicle part vendors
    return {
        "log": [f"{UNISPSC_CODE}:vet_supplier"],
        "supplier_compliance_verified": True,
        "procurement_phase": "VETTED",
    }


def allocate_funds(state: State) -> dict[str, Any]:
    """Secures financial authorization for the vehicle component purchase."""
    req_id = state.get("requisition_id", "UNKNOWN")
    auth_code = f"AUTH-{UNISPSC_SEGMENT}-{req_id}-001"

    return {
        "log": [f"{UNISPSC_CODE}:allocate_funds"],
        "budget_allocation_code": auth_code,
        "procurement_phase": "AUTHORIZED",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Emits the final procurement result and order details."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "ORDER_ISSUED",
            "requisition": state.get("requisition_id"),
            "allocation": state.get("budget_allocation_code"),
            "compliance_ok": state.get("supplier_compliance_verified"),
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_requisition)
_g.add_node("vet_supplier", vet_supplier)
_g.add_node("allocate_funds", allocate_funds)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "vet_supplier")
_g.add_edge("vet_supplier", "allocate_funds")
_g.add_edge("allocate_funds", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
