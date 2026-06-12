# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23201101 — Truck (segment 23).

This bespoke LangGraph implementation handles state transitions for vehicle
inspection, cargo loading, and dispatch authorization for industrial trucks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23201101"
UNISPSC_TITLE = "Truck"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23201101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for Truck
    maintenance_status: str
    fuel_level_percent: float
    load_weight_kg: float
    is_dispatched: bool


def inspect_vehicle(state: State) -> dict[str, Any]:
    """Verify truck mechanical readiness and fuel levels."""
    inp = state.get("input") or {}
    fuel = inp.get("initial_fuel", 100.0)
    status = "ready" if fuel > 20.0 else "needs_refuel"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_vehicle"],
        "maintenance_status": status,
        "fuel_level_percent": fuel,
    }


def load_cargo(state: State) -> dict[str, Any]:
    """Assign cargo weight to the vehicle state."""
    inp = state.get("input") or {}
    weight = float(inp.get("cargo_weight", 0.0))

    # Simple logic: cap weight at 25,000kg for standard truck
    actual_weight = min(weight, 25000.0)

    return {
        "log": [f"{UNISPSC_CODE}:load_cargo"],
        "load_weight_kg": actual_weight,
    }


def authorize_dispatch(state: State) -> dict[str, Any]:
    """Finalize manifest and authorize the truck for departure."""
    ready = state.get("maintenance_status") == "ready"
    has_load = state.get("load_weight_kg", 0.0) > 0
    dispatched = ready and has_load

    return {
        "log": [f"{UNISPSC_CODE}:authorize_dispatch"],
        "is_dispatched": dispatched,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "dispatch_status": "authorized" if dispatched else "denied",
            "telemetry": {
                "fuel": state.get("fuel_level_percent"),
                "load": state.get("load_weight_kg"),
            },
            "ok": dispatched,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_vehicle", inspect_vehicle)
_g.add_node("load_cargo", load_cargo)
_g.add_node("authorize_dispatch", authorize_dispatch)

_g.add_edge(START, "inspect_vehicle")
_g.add_edge("inspect_vehicle", "load_cargo")
_g.add_edge("load_cargo", "authorize_dispatch")
_g.add_edge("authorize_dispatch", END)

graph = _g.compile()
