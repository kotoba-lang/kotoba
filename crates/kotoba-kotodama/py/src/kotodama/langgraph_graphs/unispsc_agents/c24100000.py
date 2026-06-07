# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24100000 — Handling (segment 24).

Bespoke graph for material handling operations, safety risk assessment,
and storage allocation. This implementation manages the state transition
from initial load inspection through safety verification to final dispatch.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24100000"
UNISPSC_TITLE = "Handling"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24100000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    load_weight_kg: float
    handling_method: str
    risk_assessment: str
    storage_assignment: str


def categorize_load(state: State) -> dict[str, Any]:
    """Analyzes the input to determine the weight class and handling method."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))

    if weight > 1000:
        method = "crane_required"
    elif weight > 25:
        method = "forklift_assisted"
    else:
        method = "manual_handling"

    return {
        "log": [f"{UNISPSC_CODE}:categorize_load"],
        "load_weight_kg": weight,
        "handling_method": method,
    }


def assess_safety_risk(state: State) -> dict[str, Any]:
    """Evaluates the risk based on handling method and weight."""
    method = state.get("handling_method", "unknown")
    weight = state.get("load_weight_kg", 0.0)

    if method == "crane_required" or weight > 5000:
        risk = "high_priority"
    elif method == "forklift_assisted":
        risk = "standard_procedure"
    else:
        risk = "low_risk"

    return {
        "log": [f"{UNISPSC_CODE}:assess_safety_risk"],
        "risk_assessment": risk,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Assigns a storage location and generates the final handling manifest."""
    risk = state.get("risk_assessment", "unknown")
    method = state.get("handling_method", "unknown")

    # Logic for storage slot assignment
    slot = "ZONE-A-HEAVY" if risk == "high_priority" else "ZONE-B-GENERAL"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "storage_assignment": slot,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "dispatched",
            "handling_method": method,
            "assigned_slot": slot,
            "safety_checked": True,
        },
    }


_g = StateGraph(State)

_g.add_node("categorize_load", categorize_load)
_g.add_node("assess_safety_risk", assess_safety_risk)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "categorize_load")
_g.add_edge("categorize_load", "assess_safety_risk")
_g.add_edge("assess_safety_risk", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
