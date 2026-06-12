# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102200 — Procure (segment 21).
Bespoke logic for requisition review, vendor selection, and purchase order issuance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102200"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102200"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Procurement processing
    requisition_id: str
    budget_approved: bool
    vendor_selected: str
    purchase_order_id: str


def review_requisition(state: State) -> dict[str, Any]:
    """Validates the procurement requisition and checks budget alignment."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-UNKNOWN")
    budget_val = inp.get("budget", 0)
    # Simulation: budget is approved if it's within a specific range
    approved = budget_val > 0 and budget_val < 1000000

    return {
        "log": [f"{UNISPSC_CODE}:review_requisition"],
        "requisition_id": req_id,
        "budget_approved": approved,
    }


def select_vendor(state: State) -> dict[str, Any]:
    """Evaluates available vendors based on the requisition requirements."""
    if not state.get("budget_approved"):
        return {
            "log": [f"{UNISPSC_CODE}:select_vendor:budget_rejected"],
            "vendor_selected": "NONE",
        }

    inp = state.get("input") or {}
    vendors = inp.get("vendors", [])
    # Simulation: pick the first vendor if available, else a default
    selected = vendors[0] if vendors else "DEFAULT-VENDOR"

    return {
        "log": [f"{UNISPSC_CODE}:select_vendor:success"],
        "vendor_selected": selected,
    }


def issue_po(state: State) -> dict[str, Any]:
    """Generates a formal purchase order for the selected vendor."""
    vendor = state.get("vendor_selected")
    ok = state.get("budget_approved", False) and vendor != "NONE"
    po_id = f"PO-{state.get('requisition_id', 'REQ')}-{UNISPSC_CODE}" if ok else "INVALID"

    return {
        "log": [f"{UNISPSC_CODE}:issue_po"],
        "purchase_order_id": po_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "po_id": po_id,
            "vendor": vendor,
            "status": "issued" if ok else "failed",
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("review_requisition", review_requisition)
_g.add_node("select_vendor", select_vendor)
_g.add_node("issue_po", issue_po)

_g.add_edge(START, "review_requisition")
_g.add_edge("review_requisition", "select_vendor")
_g.add_edge("select_vendor", "issue_po")
_g.add_edge("issue_po", END)

graph = _g.compile()
