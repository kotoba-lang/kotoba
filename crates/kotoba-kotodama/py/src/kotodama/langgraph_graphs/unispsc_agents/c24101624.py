# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101624 — Crane (segment 24).

Bespoke graph implementing lifecycle logic for Crane operations, including
safety verification, reach calculation, and load dispatching. This agent
manages the state of heavy lifting equipment within the UNISPSC ecosystem.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101624"
UNISPSC_TITLE = "Crane"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101624"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Crane domain state
    load_weight_kg: float
    max_capacity_kg: float
    boom_length_m: float
    safety_lock_active: bool
    site_ready: bool


def inspect_equipment(state: State) -> dict[str, Any]:
    """Verify crane integrity and site readiness."""
    inp = state.get("input") or {}
    load = float(inp.get("load_weight", 0))
    capacity = float(inp.get("max_capacity", 100000))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_equipment: load={load}kg, capacity={capacity}kg"],
        "load_weight_kg": load,
        "max_capacity_kg": capacity,
        "site_ready": inp.get("site_cleared", True),
        "safety_lock_active": False
    }


def calculate_lift_path(state: State) -> dict[str, Any]:
    """Determine if the boom extension is safe for the current load."""
    is_safe = state.get("load_weight_kg", 0) <= state.get("max_capacity_kg", 0)
    extension = 15.0 if is_safe else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_lift_path: safe={is_safe}, extension={extension}m"],
        "boom_length_m": extension,
        "safety_lock_active": not is_safe
    }


def finalize_lift(state: State) -> dict[str, Any]:
    """Execute the operation and record results."""
    success = state.get("site_ready", False) and not state.get("safety_lock_active", True)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_lift: success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation_status": "COMPLETED" if success else "HALTED",
            "safety_violation": state.get("safety_lock_active", False),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_equipment)
_g.add_node("plan", calculate_lift_path)
_g.add_node("lift", finalize_lift)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "plan")
_g.add_edge("plan", "lift")
_g.add_edge("lift", END)

graph = _g.compile()
