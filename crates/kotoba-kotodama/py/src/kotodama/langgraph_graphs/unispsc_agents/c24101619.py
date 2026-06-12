# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101619 — Crane.
Bespoke logic for lifting equipment operations, safety validation, and load analysis.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101619"
UNISPSC_TITLE = "Crane"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101619"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Crane operations
    max_load_capacity: float
    safety_inspection_valid: bool
    current_lift_weight: float
    operational_status: str


def validate_safety(state: State) -> dict[str, Any]:
    """Ensures the crane has a valid safety certificate before proceeding."""
    inp = state.get("input") or {}
    # Defaulting to 10,000kg capacity if not specified
    capacity = float(inp.get("capacity", 10000.0))
    is_valid = inp.get("inspection_status", "PASS") == "PASS"

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety - capacity={capacity} valid={is_valid}"],
        "max_load_capacity": capacity,
        "safety_inspection_valid": is_valid,
    }


def plan_lift(state: State) -> dict[str, Any]:
    """Checks if the requested load is within the crane's safe operating limits."""
    inp = state.get("input") or {}
    weight = float(inp.get("load_weight", 0.0))
    limit = state.get("max_load_capacity", 0.0)
    safety = state.get("safety_inspection_valid", False)

    is_safe = safety and (weight <= limit)
    status = "READY" if is_safe else "ABORTED"

    return {
        "log": [f"{UNISPSC_CODE}:plan_lift - weight={weight} status={status}"],
        "current_lift_weight": weight,
        "operational_status": status,
    }


def execute_operation(state: State) -> dict[str, Any]:
    """Finalizes the crane state and emits the operational report."""
    status = state.get("operational_status", "UNKNOWN")
    success = status == "READY"

    return {
        "log": [f"{UNISPSC_CODE}:execute_operation - final_status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "success": success,
            "details": {
                "load": state.get("current_lift_weight"),
                "limit": state.get("max_load_capacity"),
                "safety_cleared": state.get("safety_inspection_valid")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_safety)
_g.add_node("plan", plan_lift)
_g.add_node("execute", execute_operation)

_g.add_edge(START, "validate")
_g.add_edge("validate", "plan")
_g.add_edge("plan", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
