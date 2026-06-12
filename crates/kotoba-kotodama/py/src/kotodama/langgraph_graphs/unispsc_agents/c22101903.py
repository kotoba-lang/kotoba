# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101903 — Gantry (segment 22).

Bespoke LangGraph implementation for Gantry operations, handling safety
verification, load balancing, and movement execution for industrial frames.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101903"
UNISPSC_TITLE = "Gantry"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Gantry domain fields
    load_weight_kg: float
    safety_cleared: bool
    alignment_verified: bool
    operator_id: str


def safety_inspection(state: State) -> dict[str, Any]:
    """Node: Inspect safety interlocks and operator credentials."""
    inp = state.get("input") or {}
    operator = inp.get("operator_id", "ANONYMOUS")
    safety_status = inp.get("safety_locks_engaged", False)

    return {
        "log": [f"{UNISPSC_CODE}:safety_inspection"],
        "operator_id": operator,
        "safety_cleared": safety_status,
    }


def load_balancing(state: State) -> dict[str, Any]:
    """Node: Calculate load stability and verify structural capacity."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))

    # Gantries have specific structural limits (e.g., 50-ton limit)
    limit = 50000.0
    is_safe = weight <= limit and state.get("safety_cleared", False)

    return {
        "log": [f"{UNISPSC_CODE}:load_balancing"],
        "load_weight_kg": weight,
        "alignment_verified": is_safe,
    }


def finalize_maneuver(state: State) -> dict[str, Any]:
    """Node: Emit the finalized operation result and status."""
    success = state.get("alignment_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_maneuver"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation_status": "COMPLETED" if success else "HALTED",
            "load_integrity": success,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("safety_inspection", safety_inspection)
_g.add_node("load_balancing", load_balancing)
_g.add_node("finalize_maneuver", finalize_maneuver)

_g.add_edge(START, "safety_inspection")
_g.add_edge("safety_inspection", "load_balancing")
_g.add_edge("load_balancing", "finalize_maneuver")
_g.add_edge("finalize_maneuver", END)

graph = _g.compile()
