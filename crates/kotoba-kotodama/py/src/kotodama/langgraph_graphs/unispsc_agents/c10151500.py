# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151500 — Live Resource (segment 10).
Bespoke implementation for lifecycle management of live biological resources.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151500"
UNISPSC_TITLE = "Live Resource"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Live Resources
    health_status: str
    transport_lot_id: str
    quarantine_verified: bool
    biological_origin: str


def intake_resource(state: State) -> dict[str, Any]:
    """Handles the initial intake and classification of the live resource."""
    inp = state.get("input") or {}
    origin = inp.get("origin", "unknown")
    lot_id = inp.get("lot_id", "PENDING-000")
    return {
        "log": [f"{UNISPSC_CODE}:intake_resource"],
        "biological_origin": origin,
        "transport_lot_id": lot_id,
        "health_status": "initial_inspection",
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks quarantine requirements and health certification."""
    origin = state.get("biological_origin")
    # Simulate verification logic based on origin data
    is_verified = origin != "unknown"
    status = "healthy" if is_verified else "quarantine_required"
    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "quarantine_verified": is_verified,
        "health_status": status,
    }


def record_disposition(state: State) -> dict[str, Any]:
    """Records the final disposition and prepares the agent result."""
    verified = state.get("quarantine_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:record_disposition"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "lot_id": state.get("transport_lot_id"),
            "health_summary": state.get("health_status"),
            "status": "APPROVED" if verified else "HELD",
            "did": UNISPSC_DID,
            "ok": verified,
        },
    }


_g = StateGraph(State)

_g.add_node("intake_resource", intake_resource)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("record_disposition", record_disposition)

_g.add_edge(START, "intake_resource")
_g.add_edge("intake_resource", "verify_compliance")
_g.add_edge("verify_compliance", "record_disposition")
_g.add_edge("record_disposition", END)

graph = _g.compile()
