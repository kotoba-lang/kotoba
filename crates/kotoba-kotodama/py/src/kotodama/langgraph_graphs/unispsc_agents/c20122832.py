# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122832 — Robot (segment 20).

Bespoke graph logic for Robot lifecycle management and telemetry processing.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122832"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122832"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Robot
    battery_level: float
    operation_mode: str
    error_codes: list[str]
    sensor_telemetry: dict[str, Any]


def initialize_robot(state: State) -> dict[str, Any]:
    """Bootstraps the robot state from input parameters."""
    inp = state.get("input") or {}
    initial_battery = float(inp.get("battery", 100.0))
    mode = "active" if initial_battery > 15.0 else "low_power_safety"

    return {
        "log": [f"{UNISPSC_CODE}:initialize_robot -> mode={mode}"],
        "battery_level": initial_battery,
        "operation_mode": mode,
        "error_codes": [],
        "sensor_telemetry": inp.get("sensors", {}),
    }


def execute_robot_task(state: State) -> dict[str, Any]:
    """Simulates robot task execution and resource consumption."""
    mode = state.get("operation_mode", "unknown")
    battery = state.get("battery_level", 0.0)

    # Simulate power consumption
    consumption = 8.5 if mode == "active" else 1.2
    new_battery = max(0.0, battery - consumption)

    execution_status = "SUCCESS" if mode == "active" else "DEFERRED_LOW_POWER"

    return {
        "log": [f"{UNISPSC_CODE}:execute_robot_task -> {execution_status}"],
        "battery_level": new_battery,
        "sensor_telemetry": {
            **state.get("sensor_telemetry", {}),
            "last_execution_status": execution_status,
            "power_draw_estimated": consumption
        }
    }


def finalize_robot_state(state: State) -> dict[str, Any]:
    """Aggregates telemetry and prepares the final agent response."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_robot_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "final_battery": state.get("battery_level"),
                "mode": state.get("operation_mode"),
                "sensors": state.get("sensor_telemetry")
            },
            "status": "online" if state.get("battery_level", 0) > 0 else "depleted",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_robot)
_g.add_node("execute", execute_robot_task)
_g.add_node("finalize", finalize_robot_state)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "execute")
_g.add_edge("execute", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
