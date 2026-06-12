# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122103 — Cleaning Robot.
Bespoke logic for autonomous floor maintenance, obstacle avoidance, and sanitation mission tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122103"
UNISPSC_TITLE = "Cleaning Robot"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122103"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Cleaning Robot
    mission_id: str
    battery_level: float
    cleaning_mode: str
    obstacle_count: int
    path_optimized: bool


def configure_mission(state: State) -> dict[str, Any]:
    """Extract mission parameters and verify hardware readiness."""
    inp = state.get("input") or {}
    m_id = inp.get("mission_id", "AUTO-20122103")
    mode = inp.get("mode", "vacuum_standard")

    # Simulated internal hardware status
    initial_battery = 100.0

    return {
        "log": [f"{UNISPSC_CODE}:configure_mission -> {m_id} in {mode} mode"],
        "mission_id": m_id,
        "cleaning_mode": mode,
        "battery_level": initial_battery,
        "path_optimized": False,
    }


def analyze_environment(state: State) -> dict[str, Any]:
    """Scan for obstacles and optimize the cleaning path."""
    mode = state.get("cleaning_mode") or "standard"
    # Simulate finding obstacles based on mode complexity
    found_obstacles = 3 if "deep" in mode.lower() else 1

    return {
        "log": [f"{UNISPSC_CODE}:analyze_environment -> detected {found_obstacles} obstacles, optimizing path"],
        "obstacle_count": found_obstacles,
        "path_optimized": True,
    }


def perform_cleaning(state: State) -> dict[str, Any]:
    """Execute the cleaning routine and generate mission summary."""
    m_id = state.get("mission_id")
    battery_start = state.get("battery_level", 100.0)
    obstacles = state.get("obstacle_count", 0)

    # Energy consumption simulation: base cost + per-obstacle penalty
    battery_final = battery_start - (5.0 + (obstacles * 1.5))

    return {
        "log": [f"{UNISPSC_CODE}:perform_cleaning -> mission {m_id} completed at {battery_final}% battery"],
        "battery_level": battery_final,
        "result": {
            "mission_id": m_id,
            "status": "SUCCESS",
            "cleaning_mode": state.get("cleaning_mode"),
            "efficiency_rating": 0.95 if state.get("path_optimized") else 0.80,
            "unispsc": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
                "segment": UNISPSC_SEGMENT,
                "did": UNISPSC_DID,
            },
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_mission)
_g.add_node("analyze", analyze_environment)
_g.add_node("perform", perform_cleaning)

_g.add_edge(START, "configure")
_g.add_edge("configure", "analyze")
_g.add_edge("analyze", "perform")
_g.add_edge("perform", END)

graph = _g.compile()
