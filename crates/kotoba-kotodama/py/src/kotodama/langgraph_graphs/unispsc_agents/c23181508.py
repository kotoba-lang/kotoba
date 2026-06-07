# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181508 — Robot (segment 23).

Bespoke logic for robot lifecycle management, diagnostics, and mission execution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181508"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Robot
    battery_level: int
    operational_status: str
    diagnostic_code: str
    safety_lock_engaged: bool


def initialize_robot(state: State) -> dict[str, Any]:
    """Prepares the robot for operation by checking power and safety locks."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:initialize_robot"],
        "battery_level": inp.get("initial_battery", 100),
        "safety_lock_engaged": True,
        "operational_status": "standby",
    }


def run_diagnostics(state: State) -> dict[str, Any]:
    """Performs system checks and disengages safety locks if clear."""
    battery = state.get("battery_level", 0)
    status = "ready" if battery > 20 else "low_power"
    diag = "OK" if status == "ready" else "BATT_LOW"

    return {
        "log": [f"{UNISPSC_CODE}:run_diagnostics:battery={battery}%:diag={diag}"],
        "diagnostic_code": diag,
        "operational_status": status,
        "safety_lock_engaged": status != "ready",
    }


def execute_mission(state: State) -> dict[str, Any]:
    """Processes the mission command and emits the final result."""
    status = state.get("operational_status")
    diag = state.get("diagnostic_code")
    inp = state.get("input") or {}
    mission_cmd = inp.get("command", "patrol")

    success = status == "ready" and diag == "OK"

    return {
        "log": [f"{UNISPSC_CODE}:execute_mission:{mission_cmd}:success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "mission_success": success,
            "final_status": status,
            "command_executed": mission_cmd if success else "none",
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_robot)
_g.add_node("diagnostics", run_diagnostics)
_g.add_node("mission", execute_mission)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "diagnostics")
_g.add_edge("diagnostics", "mission")
_g.add_edge("mission", END)

graph = _g.compile()
