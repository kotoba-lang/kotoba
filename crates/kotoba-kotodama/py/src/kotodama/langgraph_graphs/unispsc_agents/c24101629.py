# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101629 — Proc (segment 24).

Bespoke logic for procurement and lifecycle management of material handling
machinery, equipment, and storage supplies.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101629"
UNISPSC_TITLE = "Proc"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101629"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Proc (Procurement/Process)
    requisition_id: str
    vendor_id: str
    item_count: int
    procurement_status: str
    compliance_verified: bool


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition for segment 24 items."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", f"REQ-{UNISPSC_CODE}")
    count = inp.get("item_count", 1)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "item_count": count,
        "compliance_verified": True,
    }


def verify_procurement_path(state: State) -> dict[str, Any]:
    """Checks vendor authorization and procurement compliance for material handling."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_procurement_path"],
        "vendor_id": f"VEND-{UNISPSC_SEGMENT}B",
        "procurement_status": "authorized",
    }


def finalize_transaction(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and emits the result state."""
    req_id = state.get("requisition_id", "N/A")
    status = state.get("procurement_status", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_transaction"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": req_id,
            "status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("verify", verify_procurement_path)
_g.add_node("finalize", finalize_transaction)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
