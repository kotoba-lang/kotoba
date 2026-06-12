# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251505 — Industrial Bread Slicers.

Bespoke graph logic for industrial food processing machinery, specifically
handling bread slicing operations, machine safety guards, and throughput.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251505"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for industrial slicing machinery
    blade_frequency_hz: float
    safety_interlock_active: bool
    conveyor_speed_m_min: float
    processed_slice_count: int


def inspect_machine(state: State) -> dict[str, Any]:
    """Node: Validate mechanical safety interlocks and blade settings."""
    inp = state.get("input") or {}
    frequency = inp.get("frequency", 60.0)
    interlock = inp.get("safety_lock", True)
    speed = inp.get("speed", 5.0)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_machine: interlock={interlock}"],
        "blade_frequency_hz": frequency,
        "safety_interlock_active": interlock,
        "conveyor_speed_m_min": speed,
    }


def execute_operation(state: State) -> dict[str, Any]:
    """Node: Perform the industrial slicing operation."""
    if not state.get("safety_interlock_active"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_operation: ABORTED - safety interlock disengaged"],
            "processed_slice_count": 0,
        }

    inp = state.get("input") or {}
    duration_min = inp.get("duration_min", 10.0)
    speed = state.get("conveyor_speed_m_min", 5.0)

    # Calculate output based on conveyor speed and duration
    # Assume 100 slices per meter of conveyor
    slices = int(speed * duration_min * 100)

    return {
        "log": [f"{UNISPSC_CODE}:execute_operation: sliced {slices} units"],
        "processed_slice_count": slices,
    }


def emit_results(state: State) -> dict[str, Any]:
    """Node: Finalize state and prepare the agent result."""
    slices = state.get("processed_slice_count", 0)
    success = slices > 0

    return {
        "log": [f"{UNISPSC_CODE}:emit_results: status={'success' if success else 'failed'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "total_slices": slices,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_machine)
_g.add_node("execute", execute_operation)
_g.add_node("emit", emit_results)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "execute")
_g.add_edge("execute", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
