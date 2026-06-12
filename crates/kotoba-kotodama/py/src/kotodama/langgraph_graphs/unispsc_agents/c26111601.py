# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111601 — Generator (segment 26).

Bespoke LangGraph agent logic for managing electrical generator state,
including fuel monitoring, synchronization validation, and power output telemetry.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111601"
UNISPSC_TITLE = "Generator"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Generator
    fuel_level_pct: float
    load_demand_kw: float
    is_synchronized: bool
    maintenance_status: str


def inspect_systems(state: State) -> dict[str, Any]:
    """Inspects fuel levels and maintenance logs before startup."""
    inp = state.get("input") or {}
    fuel = float(inp.get("fuel_level", 100.0))
    status = "nominal" if fuel > 15.0 else "low_fuel_warning"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_systems"],
        "fuel_level_pct": fuel,
        "maintenance_status": status,
    }


def synchronize_grid(state: State) -> dict[str, Any]:
    """Simulates the synchronization of the generator frequency with the grid."""
    # Logic: Cannot synchronize if maintenance status is critical or fuel is zero
    can_sync = state.get("fuel_level_pct", 0) > 0 and state.get("maintenance_status") != "critical"

    return {
        "log": [f"{UNISPSC_CODE}:synchronize_grid"],
        "is_synchronized": can_sync,
    }


def calculate_output(state: State) -> dict[str, Any]:
    """Calculates effective power output based on load demand and sync state."""
    inp = state.get("input") or {}
    demand = float(inp.get("demand_kw", 500.0))
    synced = state.get("is_synchronized", False)

    actual_output = demand if synced else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_output"],
        "load_demand_kw": actual_output,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "active_power_kw": actual_output,
                "grid_sync": synced,
                "fuel_remaining": state.get("fuel_level_pct"),
            },
            "status": "operating" if actual_output > 0 else "idling",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_systems)
_g.add_node("synchronize", synchronize_grid)
_g.add_node("emit", calculate_output)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "synchronize")
_g.add_edge("synchronize", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
