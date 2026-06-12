# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101515"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101515"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Procure (Segment 11: Live Animals and Materials)
    health_status: str
    transport_lot_id: str
    quarantine_verified: bool
    budget_allocated: float
    vendor_license_id: str


def inspect_requisition(state: State) -> dict[str, Any]:
    """Inspects the procurement requisition for live animal materials."""
    inp = state.get("input") or {}
    lot_id = inp.get("lot_id", "LOT-PENDING")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_requisition"],
        "transport_lot_id": lot_id,
        "health_status": "pending_inspection",
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Verifies quarantine status and vendor licensing for segment 11 compliance."""
    # Simulated compliance logic for procurement of live materials
    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "quarantine_verified": True,
        "vendor_license_id": "LIC-11-9982",
        "health_status": "cleared",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and emits the result."""
    is_ok = state.get("quarantine_verified", False) and state.get("health_status") == "cleared"
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "budget_allocated": 1500.00 if is_ok else 0.0,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "lot_id": state.get("transport_lot_id"),
            "vendor_license": state.get("vendor_license_id"),
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_requisition", inspect_requisition)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "inspect_requisition")
_g.add_edge("inspect_requisition", "verify_compliance")
_g.add_edge("verify_compliance", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
