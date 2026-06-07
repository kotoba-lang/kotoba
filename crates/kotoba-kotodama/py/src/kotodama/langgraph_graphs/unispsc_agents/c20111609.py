# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20111609 — Robot (segment 20).
Bespoke logic for robot initialization, actuator calibration, and task execution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20111609"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20111609"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    battery_level: float
    diagnostic_status: str
    calibration_offset: list[float]
    safety_check_passed: bool


def initialize_systems(state: State) -> dict[str, Any]:
    """Initializes internal robot sub-systems and checks power levels."""
    inp = state.get("input") or {}
    battery = float(inp.get("initial_battery", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_systems"],
        "battery_level": battery,
        "diagnostic_status": "OK" if battery > 20 else "LOW_BATTERY",
        "safety_check_passed": battery > 10,
    }


def calibrate_actuators(state: State) -> dict[str, Any]:
    """Sets actuator calibration offsets based on environment input."""
    if not state.get("safety_check_passed"):
        return {"log": [f"{UNISPSC_CODE}:calibrate_actuators:skipped:safety_failure"]}

    inp = state.get("input") or {}
    offset = inp.get("calibration", [0.0, 0.0, 0.0, 0.0])

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_actuators"],
        "calibration_offset": offset,
    }


def execute_robotics_task(state: State) -> dict[str, Any]:
    """Finalizes the robot's action and prepares the result payload."""
    status = state.get("diagnostic_status", "UNKNOWN")
    passed = state.get("safety_check_passed", False)

    success = passed and status == "OK"

    return {
        "log": [f"{UNISPSC_CODE}:execute_robotics_task"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "COMPLETED" if success else "FAILED",
            "telemetry": {
                "battery": state.get("battery_level"),
                "calibration": state.get("calibration_offset"),
                "diagnostics": status,
            },
            "did": UNISPSC_DID,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_systems)
_g.add_node("calibrate", calibrate_actuators)
_g.add_node("execute", execute_robotics_task)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "calibrate")
_g.add_edge("calibrate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
