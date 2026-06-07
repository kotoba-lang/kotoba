# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102205 — Irrigation (segment 21).

Bespoke logic for irrigation system management, handling moisture sensors,
flow calculations, and valve actuation simulations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102205"
UNISPSC_TITLE = "Irrigation"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102205"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields
    soil_moisture_index: float
    system_pressure_psi: float
    is_valve_open: bool
    estimated_water_usage_liters: float


def validate_infrastructure(state: State) -> dict[str, Any]:
    """Check sensor health and initial system pressure."""
    inp = state.get("input") or {}
    moisture = float(inp.get("soil_moisture", 0.35))
    pressure = float(inp.get("pressure", 45.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_infrastructure: moisture={moisture}, pressure={pressure}"],
        "soil_moisture_index": moisture,
        "system_pressure_psi": pressure,
    }


def calculate_irrigation_demand(state: State) -> dict[str, Any]:
    """Determine water volume based on moisture deficit."""
    moisture = state.get("soil_moisture_index", 0.0)
    # Target moisture is 0.60
    deficit = max(0.0, 0.60 - moisture)
    # 100 liters per 0.1 deficit
    volume = deficit * 1000.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_irrigation_demand: demand={volume}L"],
        "estimated_water_usage_liters": volume,
        "is_valve_open": volume > 0,
    }


def finalize_cycle(state: State) -> dict[str, Any]:
    """Summarize the irrigation event."""
    is_open = state.get("is_valve_open", False)
    volume = state.get("estimated_water_usage_liters", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_cycle: status={'active' if is_open else 'idle'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "active": is_open,
            "volume_delivered": volume,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_infrastructure)
_g.add_node("calculate", calculate_irrigation_demand)
_g.add_node("finalize", finalize_cycle)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
