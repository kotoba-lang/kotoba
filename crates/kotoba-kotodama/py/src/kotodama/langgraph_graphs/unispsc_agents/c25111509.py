# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111509"
UNISPSC_TITLE = "Cruise Graph"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Cruise Graph
    navigation_chart_id: str
    waypoint_buffer: list[dict[str, float]]
    berth_confirmed: bool
    vessel_manifest_id: str


def initialize_cruise_plan(state: State) -> dict[str, Any]:
    """Initializes the cruise plan with navigation and vessel identifiers."""
    inp = state.get("input") or {}
    chart_id = inp.get("chart_id", "NAV-G25-ALPHA")
    manifest_id = inp.get("manifest_id", "MANIFEST-2026-X")
    return {
        "log": [f"{UNISPSC_CODE}:initialize_cruise_plan"],
        "navigation_chart_id": chart_id,
        "vessel_manifest_id": manifest_id,
        "berth_confirmed": False,
    }


def calculate_waypoints(state: State) -> dict[str, Any]:
    """Calculates navigation waypoints based on the active chart and manifest."""
    # Simulate geographic waypoint calculation for the cruise route
    waypoints = [
        {"lat": 34.0522, "lon": -118.2437},  # Los Angeles
        {"lat": 21.3069, "lon": -157.8583},  # Honolulu
        {"lat": -17.7134, "lon": 178.0650},  # Fiji
    ]
    return {
        "log": [f"{UNISPSC_CODE}:calculate_waypoints"],
        "waypoint_buffer": waypoints,
        "berth_confirmed": True,
    }


def finalize_cruise_graph(state: State) -> dict[str, Any]:
    """Finalizes the cruise graph data and prepares the agent result."""
    waypoints = state.get("waypoint_buffer", [])
    is_ready = state.get("berth_confirmed", False) and len(waypoints) > 0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_cruise_graph"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "Ready" if is_ready else "Incomplete",
            "metadata": {
                "chart": state.get("navigation_chart_id"),
                "manifest": state.get("vessel_manifest_id"),
                "waypoint_count": len(waypoints),
            },
            "ok": is_ready,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_cruise_plan)
_g.add_node("calculate", calculate_waypoints)
_g.add_node("finalize", finalize_cruise_graph)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
