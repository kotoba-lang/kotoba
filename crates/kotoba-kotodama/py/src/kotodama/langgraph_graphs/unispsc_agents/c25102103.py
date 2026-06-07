# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25102103 — Truck Procurement (segment 25).

Bespoke logic for truck procurement workflows, including requirement
validation, budget assessment, and purchase order generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25102103"
UNISPSC_TITLE = "Truck Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25102103"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for Truck Procurement
    specifications: dict[str, Any]
    budget_approved: bool
    procurement_id: str


def evaluate_specs(state: State) -> dict[str, Any]:
    """Analyzes procurement specifications for truck fleet requirements."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {"type": "heavy_duty", "count": 1, "priority": "normal"})
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_specs"],
        "specifications": specs,
    }


def approve_budget(state: State) -> dict[str, Any]:
    """Simulates financial validation for the truck procurement request."""
    specs = state.get("specifications", {})
    count = specs.get("count", 1)
    # Simple business logic: automated approval for fleets under 100 units
    is_valid = 0 < count <= 100
    return {
        "log": [f"{UNISPSC_CODE}:approve_budget"],
        "budget_approved": is_valid,
    }


def generate_outcome(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and emits the result."""
    approved = state.get("budget_approved", False)
    specs = state.get("specifications", {})

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "status": "authorized" if approved else "denied",
        "spec_summary": specs,
        "ok": approved,
    }

    return {
        "log": [f"{UNISPSC_CODE}:generate_outcome"],
        "result": res,
        "procurement_id": f"TRK-PROC-{UNISPSC_CODE}-X1" if approved else "FAILED",
    }


_g = StateGraph(State)
_g.add_node("evaluate_specs", evaluate_specs)
_g.add_node("approve_budget", approve_budget)
_g.add_node("generate_outcome", generate_outcome)

_g.add_edge(START, "evaluate_specs")
_g.add_edge("evaluate_specs", "approve_budget")
_g.add_edge("approve_budget", "generate_outcome")
_g.add_edge("generate_outcome", END)

graph = _g.compile()
