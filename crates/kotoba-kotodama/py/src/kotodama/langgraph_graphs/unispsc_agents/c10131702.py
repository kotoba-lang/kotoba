# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10131702 — Procurement (segment 10).

Bespoke graph logic for procurement workflows, including requisition validation,
vendor evaluation, and purchase order generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10131702"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10131702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Procurement
    requisition_id: str
    budget_limit: float
    vendor_id: str
    compliance_verified: bool
    po_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition and budget."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-UNDEFINED")
    budget = float(inp.get("budget", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "budget_limit": budget,
        "compliance_verified": budget > 0,
    }


def evaluate_vendors(state: State) -> dict[str, Any]:
    """Selects a qualified vendor and checks compliance requirements."""
    is_compliant = state.get("compliance_verified", False)
    vendor_id = "VEND-GOLD-01" if is_compliant else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_vendors"],
        "vendor_id": vendor_id,
        "po_status": "PENDING_APPROVAL" if is_compliant else "CANCELLED",
    }


def generate_purchase_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement cycle and emits the purchase order status."""
    status = state.get("po_status", "UNKNOWN")
    vendor = state.get("vendor_id", "NONE")

    final_ok = status == "PENDING_APPROVAL"

    return {
        "log": [f"{UNISPSC_CODE}:generate_purchase_order"],
        "po_status": "ISSUED" if final_ok else status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "requisition_id": state.get("requisition_id"),
            "vendor_id": vendor,
            "status": "SUCCESS" if final_ok else "FAILURE",
            "did": UNISPSC_DID,
            "ok": final_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_requisition", validate_requisition)
_g.add_node("evaluate_vendors", evaluate_vendors)
_g.add_node("generate_purchase_order", generate_purchase_order)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "evaluate_vendors")
_g.add_edge("evaluate_vendors", "generate_purchase_order")
_g.add_edge("generate_purchase_order", END)

graph = _g.compile()
