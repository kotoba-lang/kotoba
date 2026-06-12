# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101900 — Robot (segment 22).

This bespoke implementation handles robotic system state transitions,
simulating diagnostic checks, task execution, and telemetry reporting
within the building and construction machinery context.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101900"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101900"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Bespoke domain fields for Robot
    battery_level: float
    operation_mode: str
    sensor_data: dict[str, float]
    diagnostic_report: list[str]
    is_safe: bool


def diagnostic_check(state: State) -> dict[str, Any]:
    """Initializes system and performs a diagnostic sweep."""
    inp = state.get("input") or {}
    battery = inp.get("initial_battery", 98.5)

    report = ["CPU: OK", "Actuators: OK", "LiDAR: Calibrated"]
    is_safe = battery > 15.0

    return {
        "log": [f"{UNISPSC_CODE}:diagnostic_check"],
        "battery_level": battery,
        "operation_mode": "STANDBY",
        "diagnostic_report": report,
        "is_safe": is_safe,
    }


def execute_task(state: State) -> dict[str, Any]:
    """Simulates robotic movement or action based on input commands."""
    if not state.get("is_safe"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_task - ABORTED (Low Power)"],
            "operation_mode": "CRITICAL_SHUTDOWN",
        }

    # Simulate energy consumption during task
    new_battery = state.get("battery_level", 0.0) - 5.2

    return {
        "log": [f"{UNISPSC_CODE}:execute_task - ACTIVE"],
        "battery_level": new_battery,
        "operation_mode": "EXECUTING",
        "sensor_data": {"x": 10.5, "y": 20.1, "z": 0.0},
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Compiles the final state and result for the caller."""
    mode = state.get("operation_mode")
    battery = state.get("battery_level")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "metadata": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
                "did": UNISPSC_DID,
            },
            "telemetry": {
                "final_mode": mode,
                "remaining_battery": battery,
                "diagnostics": state.get("diagnostic_report"),
            },
            "status": "success" if mode == "EXECUTING" else "partial_success",
        },
    }


_g = StateGraph(State)

_g.add_node("diagnostic_check", diagnostic_check)
_g.add_node("execute_task", execute_task)
_g.add_node("finalize_telemetry", finalize_telemetry)

_g.add_edge(START, "diagnostic_check")
_g.add_edge("diagnostic_check", "execute_task")
_g.add_edge("execute_task", "finalize_telemetry")
_g.add_edge("finalize_telemetry", END)

graph = _g.compile()
