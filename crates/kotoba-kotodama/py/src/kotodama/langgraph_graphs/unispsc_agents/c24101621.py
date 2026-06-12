# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101621 — Crane (segment 24).

Bespoke graph logic for industrial crane operations, including lift planning,
load verification, and safety-lock sequencing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101621"
UNISPSC_TITLE = "Crane"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101621"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Crane operations
    load_weight_kg: float
    boom_extension_m: float
    safety_lock_engaged: bool
    stability_factor: float
    operational_status: str


def plan_lift(state: State) -> dict[str, Any]:
    """Analyzes lift parameters and verifies safety constraints."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))
    extension = float(inp.get("extension", 1.0))

    # Simple stability heuristic: extension * weight should be within limits
    stability = 100000.0 / (weight * extension) if weight > 0 else 1.0

    return {
        "log": [f"{UNISPSC_CODE}:plan_lift -> weight={weight}kg, ext={extension}m"],
        "load_weight_kg": weight,
        "boom_extension_m": extension,
        "stability_factor": stability,
        "safety_lock_engaged": False,
        "operational_status": "planned"
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Engages safety protocols and confirms stability."""
    stability = state.get("stability_factor", 0.0)
    can_proceed = stability > 1.2  # Safety margin requirement

    status = "safety_cleared" if can_proceed else "safety_failed"
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety -> status={status}"],
        "safety_lock_engaged": can_proceed,
        "operational_status": status
    }


def execute_operation(state: State) -> dict[str, Any]:
    """Simulates the crane maneuver and produces the final telemetry result."""
    safe = state.get("safety_lock_engaged", False)
    weight = state.get("load_weight_kg", 0.0)

    if not safe:
        return {
            "log": [f"{UNISPSC_CODE}:execute_operation -> ABORTED"],
            "result": {"ok": False, "error": "Safety protocols not met"}
        }

    return {
        "log": [f"{UNISPSC_CODE}:execute_operation -> SUCCESS"],
        "operational_status": "completed",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "final_weight": weight,
                "cycles_completed": 1,
                "safety_rating": "nominal"
            },
            "ok": True
        }
    }


_g = StateGraph(State)

_g.add_node("plan_lift", plan_lift)
_g.add_node("verify_safety", verify_safety)
_g.add_node("execute_operation", execute_operation)

_g.add_edge(START, "plan_lift")
_g.add_edge("plan_lift", "verify_safety")
_g.add_edge("verify_safety", "execute_operation")
_g.add_edge("execute_operation", END)

graph = _g.compile()
