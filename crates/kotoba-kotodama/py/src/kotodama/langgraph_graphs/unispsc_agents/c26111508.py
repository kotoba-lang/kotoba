# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111508 — Procure (segment 26).

This agent handles procurement logic for power generation machinery and accessories,
ensuring budget authorization, vendor validation, and purchase order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111508"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for "Procure"
    procurement_id: str
    budget_cleared: bool
    vendor_id: str
    order_status: str


def validate_request(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request details."""
    inp = state.get("input") or {}
    p_id = inp.get("procurement_id", "REQ-000")
    v_id = inp.get("vendor_id", "VND-UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:validate_request"],
        "procurement_id": p_id,
        "vendor_id": v_id,
        "order_status": "VALIDATED"
    }


def authorize_budget(state: State) -> dict[str, Any]:
    """Simulates the budget authorization process for power machinery."""
    inp = state.get("input") or {}
    amount = inp.get("amount", 0)
    # Simple logic: authorize if amount is within a simulated threshold
    authorized = amount < 1000000

    return {
        "log": [f"{UNISPSC_CODE}:authorize_budget"],
        "budget_cleared": authorized,
        "order_status": "AUTHORIZED" if authorized else "REJECTED_BUDGET"
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement and prepares the result payload."""
    is_cleared = state.get("budget_cleared", False)
    p_id = state.get("procurement_id")

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "procurement_id": p_id,
        "authorized": is_cleared,
        "status": "COMPLETED" if is_cleared else "FAILED",
        "ok": is_cleared,
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": res,
        "order_status": "FINALIZED" if is_cleared else "ABORTED"
    }


_g = StateGraph(State)

_g.add_node("validate", validate_request)
_g.add_node("authorize", authorize_budget)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "authorize")
_g.add_edge("authorize", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
