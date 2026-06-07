# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21111502 — Irrigation (segment 21).

Bespoke graph implementing soil moisture analysis and irrigation scheduling
logic for agricultural and landscaping applications.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21111502"
UNISPSC_TITLE = "Irrigation"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21111502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Irrigation
    soil_moisture_index: float
    zone_identifier: str
    target_flow_rate: float
    operation_window_minutes: int
    system_ready: bool


def analyze_environmental_data(state: State) -> dict[str, Any]:
    """Inspects input for soil moisture and environmental constraints."""
    inp = state.get("input") or {}
    moisture = float(inp.get("moisture_level", 45.0))
    zone = str(inp.get("zone", "primary_field"))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_environmental_data:zone={zone}:moisture={moisture}"],
        "soil_moisture_index": moisture,
        "zone_identifier": zone,
    }


def calculate_irrigation_schedule(state: State) -> dict[str, Any]:
    """Determines duration and flow based on moisture deficit."""
    moisture = state.get("soil_moisture_index", 0.0)

    # Logic: if moisture is below 30%, intensive watering; 30-60% maintenance; >60% skip.
    if moisture < 30.0:
        duration = 45
        flow = 12.5
    elif moisture < 60.0:
        duration = 15
        flow = 5.0
    else:
        duration = 0
        flow = 0.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_irrigation_schedule:duration={duration}min:flow={flow}LPM"],
        "operation_window_minutes": duration,
        "target_flow_rate": flow,
        "system_ready": duration > 0
    }


def optimize_and_emit(state: State) -> dict[str, Any]:
    """Finalizes the irrigation plan and structures the output."""
    ready = state.get("system_ready", False)
    duration = state.get("operation_window_minutes", 0)

    return {
        "log": [f"{UNISPSC_CODE}:optimize_and_emit:ready={ready}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "zone": state.get("zone_identifier"),
            "schedule": {
                "active": ready,
                "duration_minutes": duration,
                "flow_rate_target": state.get("target_flow_rate"),
            },
            "status": "authorized" if ready else "suspended_sufficient_moisture"
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_environmental_data)
_g.add_node("calculate", calculate_irrigation_schedule)
_g.add_node("emit", optimize_and_emit)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "calculate")
_g.add_edge("calculate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
