# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101724 — Conveyor (segment 24).

This module provides bespoke LangGraph logic for managing material handling
conveyor operations, including load validation, speed configuration, and
dispatch tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101724"
UNISPSC_TITLE = "Conveyor"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101724"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Conveyor systems
    load_weight_kg: float
    belt_speed_mps: float
    operational_status: str
    destination_id: str
    maintenance_alert: bool


def configure_conveyor(state: State) -> dict[str, Any]:
    """Sets initial conveyor parameters based on incoming transport request."""
    inp = state.get("input") or {}
    speed = float(inp.get("speed", 1.2))
    dest = str(inp.get("destination", "PRIMARY_SORT"))

    return {
        "log": [f"{UNISPSC_CODE}:configure_conveyor -> speed={speed}m/s, dest={dest}"],
        "belt_speed_mps": speed,
        "destination_id": dest,
        "operational_status": "initializing",
        "maintenance_alert": False
    }


def validate_load(state: State) -> dict[str, Any]:
    """Checks if the item weight is within the conveyor's safe operating limit."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))
    max_capacity = 500.0  # KG

    is_safe = weight <= max_capacity
    status = "ready" if is_safe else "halted_overload"

    return {
        "log": [f"{UNISPSC_CODE}:validate_load -> weight={weight}kg, status={status}"],
        "load_weight_kg": weight,
        "operational_status": status,
        "maintenance_alert": not is_safe
    }


def dispatch_load(state: State) -> dict[str, Any]:
    """Finalizes the transport process and records the transaction."""
    status = state.get("operational_status")
    success = status == "ready"

    final_status = "delivered" if success else "rejected"

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_load -> {final_status}"],
        "operational_status": "idle",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "transport_outcome": final_status,
            "metrics": {
                "weight": state.get("load_weight_kg"),
                "speed": state.get("belt_speed_mps"),
                "destination": state.get("destination_id")
            },
            "ok": success
        }
    }


_g = StateGraph(State)

_g.add_node("configure", configure_conveyor)
_g.add_node("validate", validate_load)
_g.add_node("dispatch", dispatch_load)

_g.add_edge(START, "configure")
_g.add_edge("configure", "validate")
_g.add_edge("validate", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
