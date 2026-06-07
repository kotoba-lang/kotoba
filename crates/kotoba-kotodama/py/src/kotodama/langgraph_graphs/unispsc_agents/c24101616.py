# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101616 — Lifting (segment 24).

Bespoke graph logic for lifting operations, focusing on safety parameters,
load validation, and rigging configuration for industrial material handling.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101616"
UNISPSC_TITLE = "Lifting"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101616"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    load_weight_kg: float
    rigging_verified: bool
    safety_clearance: bool
    equipment_id: str
    max_capacity_kg: float


def validate_load(state: State) -> dict[str, Any]:
    """Inspects the load requirements and compares against equipment capacity."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))
    capacity = float(inp.get("capacity", 5000.0))
    equipment = str(inp.get("equipment", "standard-hoist-01"))

    # Basic safety threshold: weight must be within capacity
    is_safe = 0 < weight <= capacity

    return {
        "log": [f"{UNISPSC_CODE}:validate_load(weight={weight}, capacity={capacity}, safe={is_safe})"],
        "load_weight_kg": weight,
        "max_capacity_kg": capacity,
        "equipment_id": equipment,
        "safety_clearance": is_safe
    }


def verify_rigging(state: State) -> dict[str, Any]:
    """Ensures rigging hardware matches the load weight requirements."""
    weight = state.get("load_weight_kg", 0.0)
    is_clear = state.get("safety_clearance", False)

    # Logic for rigging selection based on load magnitude
    rigging_tier = "light-duty" if weight < 1000 else "heavy-duty"
    verified = is_clear and weight > 0

    return {
        "log": [f"{UNISPSC_CODE}:verify_rigging(tier={rigging_tier}, verified={verified})"],
        "rigging_verified": verified,
    }


def finalize_lift_plan(state: State) -> dict[str, Any]:
    """Finalizes the operation result based on safety and rigging checks."""
    verified = state.get("rigging_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_lift_plan(status={'authorized' if verified else 'denied'})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "load_kg": state.get("load_weight_kg"),
            "equipment": state.get("equipment_id"),
            "authorized": verified,
            "ok": verified,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_load", validate_load)
_g.add_node("verify_rigging", verify_rigging)
_g.add_node("finalize_lift_plan", finalize_lift_plan)

_g.add_edge(START, "validate_load")
_g.add_edge("validate_load", "verify_rigging")
_g.add_edge("verify_rigging", "finalize_lift_plan")
_g.add_edge("finalize_lift_plan", END)

graph = _g.compile()
