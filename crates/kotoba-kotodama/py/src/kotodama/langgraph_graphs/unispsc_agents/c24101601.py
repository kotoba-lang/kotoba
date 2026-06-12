# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101601 — Elevator (segment 24).
Bespoke implementation for material handling elevators and lifts.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101601"
UNISPSC_TITLE = "Elevator"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for elevator operation
    current_floor: int
    target_floor: int
    load_weight_kg: float
    safety_check_passed: bool
    door_status: str


def inspect_safety(state: State) -> dict[str, Any]:
    """Validates the elevator's safety parameters and weight capacity."""
    inp = state.get("input") or {}
    weight = inp.get("load_weight_kg", 0.0)
    max_capacity = 2500.0  # Standard freight capacity

    passed = weight <= max_capacity
    return {
        "log": [f"{UNISPSC_CODE}:inspect_safety - weight={weight}kg, passed={passed}"],
        "load_weight_kg": weight,
        "safety_check_passed": passed,
        "current_floor": inp.get("current_floor", 0),
        "target_floor": inp.get("target_floor", 0),
        "door_status": "closed"
    }


def execute_transit(state: State) -> dict[str, Any]:
    """Simulates the vertical movement of the elevator unit."""
    if not state.get("safety_check_passed"):
        return {"log": [f"{UNISPSC_CODE}:execute_transit - ABORTED (overload/safety)"]}

    start = state.get("current_floor", 0)
    end = state.get("target_floor", 0)

    return {
        "log": [f"{UNISPSC_CODE}:execute_transit - moving from floor {start} to {end}"],
        "current_floor": end,
        "door_status": "opening"
    }


def emit_arrival(state: State) -> dict[str, Any]:
    """Logs arrival and provides the final telemetry result."""
    success = state.get("safety_check_passed", False)
    current = state.get("current_floor", 0)

    return {
        "log": [f"{UNISPSC_CODE}:emit_arrival - reached floor {current}"],
        "door_status": "open",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "docked" if success else "locked",
            "floor": current,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_safety", inspect_safety)
_g.add_node("execute_transit", execute_transit)
_g.add_node("emit_arrival", emit_arrival)

_g.add_edge(START, "inspect_safety")
_g.add_edge("inspect_safety", "execute_transit")
_g.add_edge("execute_transit", "emit_arrival")
_g.add_edge("emit_arrival", END)

graph = _g.compile()
