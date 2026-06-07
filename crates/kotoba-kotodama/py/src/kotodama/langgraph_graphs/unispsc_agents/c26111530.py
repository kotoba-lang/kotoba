# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111530 — Procure.

This bespoke graph manages the procurement lifecycle for power generation
machinery, including requisition validation, budget verification, and
purchase execution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111530"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111530"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Procurement
    requisition_id: str
    vendor_selection: str
    budget_verified: bool
    procurement_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition details."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-DEFAULT")

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition:{req_id}"],
        "requisition_id": req_id,
        "procurement_status": "validated",
    }


def verify_budget(state: State) -> dict[str, Any]:
    """Simulates internal budget approval and vendor vetting."""
    req_id = state.get("requisition_id")
    # Simulate selecting a preferred vendor for power equipment
    vendor = "PowerGen-Global-Solutions"

    return {
        "log": [f"{UNISPSC_CODE}:verify_budget:approved_for_{req_id}"],
        "vendor_selection": vendor,
        "budget_verified": True,
        "procurement_status": "budget_approved",
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement and emits the transaction record."""
    vendor = state.get("vendor_selection")
    req_id = state.get("requisition_id")

    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement:finalized"],
        "procurement_status": "completed",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": req_id,
            "vendor": vendor,
            "status": "ORDER_PLACED",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_requisition", validate_requisition)
_g.add_node("verify_budget", verify_budget)
_g.add_node("execute_procurement", execute_procurement)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "verify_budget")
_g.add_edge("verify_budget", "execute_procurement")
_g.add_edge("execute_procurement", END)

graph = _g.compile()
