# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202607 — Procure (segment 25).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202607"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202607"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for vehicle procurement
    requisition_id: str
    vendor_auth_code: str
    procurement_priority: str
    compliance_verified: bool
    total_quote: float


def intake_procurement_request(state: State) -> dict[str, Any]:
    """Processes the initial procurement requisition for vehicles/components."""
    inp = state.get("input") or {}
    req_id = inp.get("req_id", "PROC-AUTO-DEFAULT")
    priority = inp.get("priority", "routine")

    return {
        "log": [f"{UNISPSC_CODE}:intake_procurement_request"],
        "requisition_id": req_id,
        "procurement_priority": priority,
        "total_quote": float(inp.get("quote", 0.0))
    }


def verify_vendor_compliance(state: State) -> dict[str, Any]:
    """Verifies that the vendor is authorized for segment 25 procurement."""
    # Logic: Routine priority is automatically compliant; others require manual override simulation
    priority = state.get("procurement_priority")
    is_verified = True if priority == "routine" else False

    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor_compliance"],
        "compliance_verified": is_verified,
        "vendor_auth_code": "V-25-CERT-99" if is_verified else "V-PENDING"
    }


def execute_procurement_order(state: State) -> dict[str, Any]:
    """Finalizes the order based on compliance results."""
    is_verified = state.get("compliance_verified", False)
    quote = state.get("total_quote", 0.0)

    # Successful execution requires verification and a non-zero quote
    success = is_verified and quote > 0

    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_id": f"ORD-{state.get('requisition_id')}",
            "status": "COMPLETED" if success else "FLAGGED_FOR_REVIEW",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("intake", intake_procurement_request)
_g.add_node("verify", verify_vendor_compliance)
_g.add_node("execute", execute_procurement_order)

_g.add_edge(START, "intake")
_g.add_edge("intake", "verify")
_g.add_edge("verify", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
