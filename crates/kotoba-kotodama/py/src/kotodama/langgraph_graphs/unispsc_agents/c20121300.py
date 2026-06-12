# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121300 — Procure (segment 20).

Bespoke agent implementation for handling procurement operations related to
mining and well drilling machinery and services.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121300"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121300"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific procurement state fields
    requisition_id: str
    vendor_verified: bool
    budget_approved: bool
    compliance_token: str
    procurement_phase: str


def initiate_procurement(state: State) -> dict[str, Any]:
    """Node 1: Initialize the procurement requisition from input data."""
    inp = state.get("input") or {}
    req_id = inp.get("req_id", f"REQ-{UNISPSC_CODE}-DEFAULT")

    return {
        "log": [f"{UNISPSC_CODE}:initiate_procurement:{req_id}"],
        "requisition_id": req_id,
        "procurement_phase": "INITIALIZED",
        "vendor_verified": "vendor_id" in inp,
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Node 2: Verify vendor compliance and budget authorization."""
    # Simulate internal business logic for procurement compliance
    is_vendor_ok = state.get("vendor_verified", False)
    req_id = state.get("requisition_id", "UNKNOWN")

    # Simple simulated token generation
    token = f"AUTH-{req_id[:4]}-2026-X"

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance:ok={is_vendor_ok}"],
        "budget_approved": True,
        "compliance_token": token,
        "procurement_phase": "VERIFIED",
    }


def generate_procurement_result(state: State) -> dict[str, Any]:
    """Node 3: Finalize the state and emit the procurement outcome."""
    phase = state.get("procurement_phase", "UNKNOWN")
    token = state.get("compliance_token", "NONE")

    return {
        "log": [f"{UNISPSC_CODE}:generate_procurement_result:{phase}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": state.get("requisition_id"),
            "authorization_token": token,
            "status": "APPROVED" if state.get("budget_approved") else "PENDING",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("initiate", initiate_procurement)
_g.add_node("verify", verify_compliance)
_g.add_node("finalize", generate_procurement_result)

_g.add_edge(START, "initiate")
_g.add_edge("initiate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
