# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101728 — Conveyor (segment 24).

Bespoke graph logic for automated material handling systems. This agent
manages the lifecycle of a discrete item or bulk material unit as it
traverses a conveyor assembly, handling weight validation, flow
monitoring, and routing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101728"
UNISPSC_TITLE = "Conveyor"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101728"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Conveyor operations
    load_weight_kg: float
    belt_speed_mps: float
    jam_sensor_tripped: bool
    destination_gate: str
    maintenance_status: str


def initialize_conveyor(state: State) -> dict[str, Any]:
    """Prepares the conveyor belt for the incoming load."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))
    dest = str(inp.get("destination", "main_stack"))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_conveyor"],
        "load_weight_kg": weight,
        "destination_gate": dest,
        "belt_speed_mps": 0.5 if weight < 50 else 0.2,
        "maintenance_status": "nominal"
    }


def monitor_flow(state: State) -> dict[str, Any]:
    """Simulates real-time sensor monitoring of the belt flow."""
    weight = state.get("load_weight_kg", 0.0)
    # Simulate a jam if the weight exceeds design limits
    jammed = weight > 500.0
    status = "alert:overload" if jammed else "nominal"

    return {
        "log": [f"{UNISPSC_CODE}:monitor_flow"],
        "jam_sensor_tripped": jammed,
        "maintenance_status": status
    }


def route_item(state: State) -> dict[str, Any]:
    """Finalizes the transfer and records the routing result."""
    jammed = state.get("jam_sensor_tripped", False)
    dest = state.get("destination_gate", "unknown")

    success = not jammed
    final_location = dest if success else "emergency_stop_buffer"

    return {
        "log": [f"{UNISPSC_CODE}:route_item"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "routing_completed": success,
            "final_location": final_location,
            "throughput_metrics": {
                "weight": state.get("load_weight_kg"),
                "speed": state.get("belt_speed_mps")
            }
        }
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_conveyor)
_g.add_node("monitor", monitor_flow)
_g.add_node("route", route_item)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "monitor")
_g.add_edge("monitor", "route")
_g.add_edge("route", END)

graph = _g.compile()
