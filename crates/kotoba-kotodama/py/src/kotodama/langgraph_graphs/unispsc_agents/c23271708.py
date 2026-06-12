# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271708 — Procure (segment 23).
Bespoke logic for handling procurement workflows.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271708"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271708"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for "Procure"
    requisition_id: str
    budget_cleared: bool
    vendor_id: str
    procurement_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition and checks budget limits."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-GEN-001")
    amount = inp.get("amount", 0)

    # Simple logic: auto-clear if amount is within a standard threshold
    budget_ok = 0 < amount < 100000

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "budget_cleared": budget_ok,
        "procurement_status": "VALIDATED" if budget_ok else "EXCEEDS_LIMIT"
    }


def select_vendor(state: State) -> dict[str, Any]:
    """Selects an approved vendor for the procurement request."""
    if not state.get("budget_cleared"):
        return {
            "log": [f"{UNISPSC_CODE}:select_vendor:skipped"],
            "procurement_status": "HOLD_FOR_BUDGET"
        }

    return {
        "log": [f"{UNISPSC_CODE}:select_vendor:assigned"],
        "vendor_id": "VEND-ASSET-77",
        "procurement_status": "READY"
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Prepares the final procurement result and success confirmation."""
    status = state.get("procurement_status", "UNKNOWN")
    vendor = state.get("vendor_id", "PENDING")
    req_id = state.get("requisition_id", "N/A")

    is_success = status == "READY"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_info": {
                "requisition_id": req_id,
                "vendor_id": vendor,
                "status": status,
            },
            "ok": is_success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requisition)
_g.add_node("select_vendor", select_vendor)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "select_vendor")
_g.add_edge("select_vendor", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
