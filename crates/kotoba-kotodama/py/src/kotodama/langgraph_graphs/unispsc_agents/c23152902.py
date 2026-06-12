# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23152902 — Robot (segment 23).
Bespoke logic for industrial and service robots.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23152902"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23152902"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Extra domain fields for "Robot"
    battery_level: float
    operational_mode: str
    maintenance_status: str
    telemetry_data: dict[str, Any]
    mission_id: str


def initialize_robot(state: State) -> dict[str, Any]:
    """Node: Validate system readiness and initialize mission parameters."""
    inp = state.get("input") or {}
    mission_id = inp.get("mission_id", "mission-default")
    return {
        "log": [f"{UNISPSC_CODE}:initialize_robot"],
        "battery_level": 100.0,
        "operational_mode": "idle",
        "maintenance_status": "ready",
        "mission_id": mission_id,
    }


def execute_mission(state: State) -> dict[str, Any]:
    """Node: Process the core robotic logic/actions."""
    mode = "active" if state.get("maintenance_status") == "ready" else "fault"
    current_battery = state.get("battery_level", 0.0) - 15.5

    return {
        "log": [f"{UNISPSC_CODE}:execute_mission"],
        "operational_mode": mode,
        "battery_level": max(0.0, current_battery),
        "telemetry_data": {
            "status": "in_progress",
            "position": {"x": 10.5, "y": 20.0},
            "sensor_ok": True,
        },
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Node: Package result and finalize log."""
    mission_id = state.get("mission_id")
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "operational_mode": "shutdown",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "mission_id": mission_id,
            "final_battery": state.get("battery_level"),
            "telemetry": state.get("telemetry_data"),
            "did": UNISPSC_DID,
            "status": "completed",
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_robot)
_g.add_node("execute", execute_mission)
_g.add_node("finalize", finalize_telemetry)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "execute")
_g.add_edge("execute", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
