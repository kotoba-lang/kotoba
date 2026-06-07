# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121005 — Robot (segment 20).

Bespoke graph logic for robotic systems lifecycle management, including
initialization, diagnostic self-tests, and operational mission execution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121005"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121005"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Robot
    battery_level: int
    firmware_version: str
    diagnostics_passed: bool
    operational_mode: str


def initialize_robot(state: State) -> dict[str, Any]:
    """Sets initial power levels and loads system configuration."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:initialize_robot"],
        "battery_level": inp.get("initial_battery", 100),
        "firmware_version": "v2.0.4-stable",
        "operational_mode": "STANDBY",
    }


def perform_diagnostics(state: State) -> dict[str, Any]:
    """Runs hardware integrity checks and sensor calibration."""
    battery = state.get("battery_level", 0)
    passed = battery > 15
    return {
        "log": [f"{UNISPSC_CODE}:perform_diagnostics - passed={passed}"],
        "diagnostics_passed": passed,
        "operational_mode": "DIAGNOSTIC" if not passed else "READY",
    }


def execute_mission(state: State) -> dict[str, Any]:
    """Executes the primary robotic task if systems are clear."""
    diagnostics = state.get("diagnostics_passed", False)
    if diagnostics:
        mission_report = "Mission successful: Parameters within tolerance."
        mode = "ACTIVE"
    else:
        mission_report = "Mission aborted: Critical diagnostic failure."
        mode = "MAINTENANCE"

    return {
        "log": [f"{UNISPSC_CODE}:execute_mission - {mode}"],
        "operational_mode": mode,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mission_report": mission_report,
            "final_mode": mode,
            "ok": diagnostics,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_robot)
_g.add_node("diagnostics", perform_diagnostics)
_g.add_node("execute", execute_mission)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "diagnostics")
_g.add_edge("diagnostics", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
