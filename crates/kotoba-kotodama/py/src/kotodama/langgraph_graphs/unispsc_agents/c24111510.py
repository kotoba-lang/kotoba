# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111510 — Procurement (segment 24).
Bespoke logic for requisition validation, vendor compliance, and procurement finalization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111510"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Procurement processing
    requisition_valid: bool
    vendor_qualified: bool
    budget_authorized: bool
    procurement_id: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the procurement requisition and checks budget availability."""
    inp = state.get("input") or {}
    req_data = inp.get("requisition", {})
    is_valid = bool(req_data.get("id"))
    # Default to 1M if available_budget is not provided for simulation purposes
    has_budget = req_data.get("amount", 0) <= inp.get("available_budget", 1000000)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_valid": is_valid,
        "budget_authorized": has_budget,
    }


def qualify_vendor(state: State) -> dict[str, Any]:
    """Evaluates vendor credentials and compliance status."""
    if not state.get("requisition_valid") or not state.get("budget_authorized"):
        return {
            "log": [f"{UNISPSC_CODE}:qualify_vendor:skipped"],
            "vendor_qualified": False,
        }

    inp = state.get("input") or {}
    vendor_data = inp.get("vendor", {})
    # Simple qualification logic: vendor must have a rating >= 3.0
    qualified = vendor_data.get("rating", 0) >= 3.0 if vendor_data else False

    return {
        "log": [f"{UNISPSC_CODE}:qualify_vendor"],
        "vendor_qualified": qualified,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final procurement record and result."""
    ok = (state.get("requisition_valid", False) and
          state.get("budget_authorized", False) and
          state.get("vendor_qualified", False))

    req_id = state.get("input", {}).get("requisition", {}).get("id", "NA")
    proc_id = f"PROC-{UNISPSC_CODE}-{req_id}" if ok else "DENIED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "procurement_id": proc_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "procurement_id": proc_id,
            "status": "approved" if ok else "rejected",
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_requisition", validate_requisition)
_g.add_node("qualify_vendor", qualify_vendor)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "qualify_vendor")
_g.add_edge("qualify_vendor", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
