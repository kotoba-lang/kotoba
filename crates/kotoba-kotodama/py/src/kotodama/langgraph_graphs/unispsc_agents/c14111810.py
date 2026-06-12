# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111810 — Procurement (segment 14).

This agent manages the procurement lifecycle for paper materials,
including requisition validation, vendor selection based on budgetary
constraints, and final order authorization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111810"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111810"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    requisition_id: str
    budget_limit: float
    vendor_authorized: bool
    procurement_phase: str


def validate_request(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-P-1411")
    budget = float(inp.get("budget", 5000.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_request"],
        "requisition_id": req_id,
        "budget_limit": budget,
        "procurement_phase": "VALIDATED",
    }


def evaluate_vendors(state: State) -> dict[str, Any]:
    budget = state.get("budget_limit", 0.0)
    # Simple logic: authorize if budget is within reasonable range
    authorized = 0 < budget < 1000000
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_vendors"],
        "vendor_authorized": authorized,
        "procurement_phase": "EVALUATED",
    }


def authorize_purchase(state: State) -> dict[str, Any]:
    authorized = state.get("vendor_authorized", False)
    phase = "AUTHORIZED" if authorized else "DECLINED"
    return {
        "log": [f"{UNISPSC_CODE}:authorize_purchase"],
        "procurement_phase": phase,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": state.get("requisition_id"),
            "status": phase,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_request", validate_request)
_g.add_node("evaluate_vendors", evaluate_vendors)
_g.add_node("authorize_purchase", authorize_purchase)

_g.add_edge(START, "validate_request")
_g.add_edge("validate_request", "evaluate_vendors")
_g.add_edge("evaluate_vendors", "authorize_purchase")
_g.add_edge("authorize_purchase", END)

graph = _g.compile()
