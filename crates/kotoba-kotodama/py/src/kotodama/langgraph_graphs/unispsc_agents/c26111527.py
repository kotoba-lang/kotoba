# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111527 — Motion Control (segment 26).

Bespoke graph logic for motion control systems, focusing on axis initialization,
trajectory planning, and motion dispatch.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111527"
UNISPSC_TITLE = "Motion Control"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111527"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Motion Control
    axis_status: str
    trajectory_points: list[tuple[float, float]]
    pid_tuned: bool
    safety_interlock: bool


def initialize_controller(state: State) -> dict[str, Any]:
    """Pre-flight checks for the motion control axis."""
    inp = state.get("input") or {}
    axis_id = inp.get("axis_id", "AXIS_0")
    return {
        "log": [f"{UNISPSC_CODE}:initialize_controller: axis {axis_id} active"],
        "axis_status": "READY",
        "safety_interlock": True,
        "pid_tuned": inp.get("optimize", False),
    }


def compute_trajectory(state: State) -> dict[str, Any]:
    """Calculates the motion path based on input parameters."""
    points = [(0.0, 0.0), (10.0, 5.0), (20.0, 10.0)]
    return {
        "log": [f"{UNISPSC_CODE}:compute_trajectory: generated {len(points)} setpoints"],
        "trajectory_points": points,
        "axis_status": "PLANNING_COMPLETE",
    }


def dispatch_motion(state: State) -> dict[str, Any]:
    """Simulates the execution of the motion command."""
    success = state.get("safety_interlock", False)
    status = "EXECUTED" if success else "FAILED_INTERLOCK"

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_motion: status {status}"],
        "axis_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "motion_status": status,
            "point_count": len(state.get("trajectory_points", [])),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize_controller", initialize_controller)
_g.add_node("compute_trajectory", compute_trajectory)
_g.add_node("dispatch_motion", dispatch_motion)

_g.add_edge(START, "initialize_controller")
_g.add_edge("initialize_controller", "compute_trajectory")
_g.add_edge("compute_trajectory", "dispatch_motion")
_g.add_edge("dispatch_motion", END)

graph = _g.compile()
