# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102403 — Procurement (segment 21).

Bespoke logic for procurement requisition evaluation and vendor verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102403"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102403"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields
    vendor_id: str
    requisition_value: float
    approval_status: str
    po_number: str


def evaluate_requisition(state: State) -> dict[str, Any]:
    """Inspects the input for procurement amount and vendor details."""
    inp = state.get("input") or {}
    val = float(inp.get("amount", 0.0))
    vendor = str(inp.get("vendor", "UNKNOWN"))

    # Logical threshold for automatic processing
    status = "PENDING_VERIFICATION" if val > 0 else "INVALID_REQUEST"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_requisition"],
        "requisition_value": val,
        "vendor_id": vendor,
        "approval_status": status
    }


def verify_vendor(state: State) -> dict[str, Any]:
    """Checks if the vendor is in the approved registry."""
    vendor = state.get("vendor_id", "UNKNOWN")
    # Mock registry check: vendors starting with 'V-' are approved
    is_approved = vendor.upper().startswith("V-")

    current_status = state.get("approval_status")
    if is_approved:
        next_status = "VENDOR_VERIFIED"
    else:
        next_status = "UNAUTHORIZED_VENDOR"

    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor"],
        "approval_status": next_status
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates a purchase order reference if verification passed."""
    status = state.get("approval_status")
    val = state.get("requisition_value", 0.0)

    success = status == "VENDOR_VERIFIED" and val > 0
    po_ref = f"PO-{UNISPSC_CODE}-{int(val)}" if success else "NONE"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "po_number": po_ref,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "po_reference": po_ref,
            "status": "APPROVED" if success else "REJECTED",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("evaluate", evaluate_requisition)
_g.add_node("verify", verify_vendor)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
