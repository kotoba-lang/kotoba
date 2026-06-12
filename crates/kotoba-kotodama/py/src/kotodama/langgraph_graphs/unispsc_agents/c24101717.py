# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101717 — Conveyor (segment 24).

Bespoke graph logic for industrial conveyor systems, handling speed regulation,
load monitoring, and automated transport state transitions.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101717"
UNISPSC_TITLE = "Conveyor"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101717"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Conveyor
    belt_speed_mps: float
    current_load_kg: float
    safety_interlock_active: bool
    destination_reached: bool


def initialize_conveyor(state: State) -> dict[str, Any]:
    """Sets initial operational parameters based on input."""
    inp = state.get("input") or {}
    speed = float(inp.get("speed", 1.5))
    load = float(inp.get("load", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_conveyor: speed={speed}mps, load={load}kg"],
        "belt_speed_mps": speed,
        "current_load_kg": load,
        "safety_interlock_active": False,
    }


def monitor_load(state: State) -> dict[str, Any]:
    """Simulates real-time monitoring of the conveyor belt load and health."""
    load = state.get("current_load_kg", 0.0)
    safety = load > 500.0  # Threshold for safety interlock

    log_entry = f"{UNISPSC_CODE}:monitor_load: load={load}kg"
    if safety:
        log_entry += " [WARNING: HIGH LOAD]"

    return {
        "log": [log_entry],
        "safety_interlock_active": safety,
        "destination_reached": not safety, # If safety is triggered, we haven't reached destination safely
    }


def finalize_transport(state: State) -> dict[str, Any]:
    """Finalizes the transport process and prepares the result metadata."""
    success = state.get("destination_reached", False) and not state.get("safety_interlock_active", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_transport: success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "transport_status": "COMPLETED" if success else "HALTED",
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_conveyor)
_g.add_node("monitor", monitor_load)
_g.add_node("finalize", finalize_transport)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "monitor")
_g.add_edge("monitor", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
