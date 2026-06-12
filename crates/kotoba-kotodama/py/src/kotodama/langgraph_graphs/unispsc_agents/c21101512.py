# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101512 — Irrigation.

Bespoke graph logic for managing irrigation cycles based on moisture sensors
and water source availability.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101512"
UNISPSC_TITLE = "Irrigation"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101512"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Irrigation
    soil_moisture_percent: float
    irrigation_active: bool
    water_source_level_percent: float
    scheduled_duration_minutes: int


def analyze_environmental_data(state: State) -> dict[str, Any]:
    """Reads sensor inputs and initializes domain state."""
    inp = state.get("input") or {}
    # Defaulting to 45% moisture and 80% source level if not provided
    moisture = float(inp.get("moisture_reading", 45.0))
    source_level = float(inp.get("source_level", 80.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_environmental_data"],
        "soil_moisture_percent": moisture,
        "water_source_level_percent": source_level,
    }


def optimize_irrigation_schedule(state: State) -> dict[str, Any]:
    """Determines if watering is necessary and for how long."""
    moisture = state.get("soil_moisture_percent", 50.0)
    source = state.get("water_source_level_percent", 0.0)

    # Logic: Only water if moisture is low and we have sufficient water
    is_dry = moisture < 35.0
    has_water = source > 15.0

    should_irrigate = is_dry and has_water
    duration = 0
    if should_irrigate:
        # Heavily dry needs more time
        duration = 45 if moisture < 15.0 else 20

    return {
        "log": [f"{UNISPSC_CODE}:optimize_irrigation_schedule"],
        "irrigation_active": should_irrigate,
        "scheduled_duration_minutes": duration,
    }


def finalize_irrigation_report(state: State) -> dict[str, Any]:
    """Generates the final outcome for the irrigation actor."""
    active = state.get("irrigation_active", False)
    duration = state.get("scheduled_duration_minutes", 0)
    moisture = state.get("soil_moisture_percent", 0.0)

    status_msg = "IRRIGATION_COMMENCED" if active else "SOIL_MOISTURE_SUFFICIENT"
    if active and duration == 0:
        status_msg = "INSUFFICIENT_WATER_SOURCE"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_irrigation_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": status_msg,
            "action_taken": "ACTIVATE_PUMPS" if active else "MONITOR_ONLY",
            "runtime_estimate": f"{duration}m",
            "telemetry": {
                "moisture": f"{moisture}%",
                "source": f"{state.get('water_source_level_percent')}%"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_environmental_data)
_g.add_node("optimize", optimize_irrigation_schedule)
_g.add_node("report", finalize_irrigation_report)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "optimize")
_g.add_edge("optimize", "report")
_g.add_edge("report", END)

graph = _g.compile()
