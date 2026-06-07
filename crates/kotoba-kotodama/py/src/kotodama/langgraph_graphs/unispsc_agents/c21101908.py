# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101908 — Irrigation.

This agent handles irrigation scheduling by assessing moisture levels,
calculating hydraulic requirements, and generating dispatch orders.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101908"
UNISPSC_TITLE = "Irrigation"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101908"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific irrigation state
    water_source: str
    moisture_deficit_pct: float
    irrigation_duration_min: int
    system_pressure_psi: float


def assess_field_state(state: State) -> dict[str, Any]:
    """Analyze current vs target moisture to determine the water deficit."""
    inp = state.get("input") or {}
    current = inp.get("current_moisture_level", 25.0)
    target = inp.get("target_moisture_level", 45.0)

    # Simple linear deficit calculation
    deficit = max(0.0, target - current)

    return {
        "log": [f"{UNISPSC_CODE}:assess_field_state"],
        "moisture_deficit_pct": deficit,
        "water_source": inp.get("source_id", "primary_well"),
        "system_pressure_psi": inp.get("operating_pressure", 50.0)
    }


def calculate_hydraulic_load(state: State) -> dict[str, Any]:
    """Calculate the required duration based on the moisture deficit."""
    deficit = state.get("moisture_deficit_pct", 0.0)
    pressure = state.get("system_pressure_psi", 50.0)

    # Model: 1% deficit requires 12 minutes at standard 50 PSI
    base_duration = deficit * 12.0
    # Efficiency adjustment based on pressure (simplified)
    pressure_factor = 50.0 / pressure if pressure > 0 else 1.0
    final_duration = int(base_duration * pressure_factor)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_hydraulic_load"],
        "irrigation_duration_min": final_duration
    }


def generate_dispatch_order(state: State) -> dict[str, Any]:
    """Finalize the irrigation schedule and prepare the result payload."""
    duration = state.get("irrigation_duration_min", 0)
    source = state.get("water_source", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:generate_dispatch_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "active" if duration > 0 else "idle",
            "schedule": {
                "duration_minutes": duration,
                "source": source,
                "priority": "standard" if duration < 60 else "high"
            },
            "verification_required": duration > 120
        }
    }


_g = StateGraph(State)

_g.add_node("assess", assess_field_state)
_g.add_node("calculate", calculate_hydraulic_load)
_g.add_node("dispatch", generate_dispatch_order)

_g.add_edge(START, "assess")
_g.add_edge("assess", "calculate")
_g.add_edge("calculate", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
