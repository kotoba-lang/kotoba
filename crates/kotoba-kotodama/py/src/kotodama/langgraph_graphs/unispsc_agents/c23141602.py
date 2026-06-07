# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23141602 — Robot (segment 23).

Bespoke robotics logic implementing a diagnostic-actuation-telemetry pipeline.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23141602"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23141602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Robot Domain Fields
    battery_level: float
    sensor_calibration: bool
    actuator_status: str
    telemetry_data: dict[str, Any]


def power_on_self_test(state: State) -> dict[str, Any]:
    """Perform initial diagnostics on the robot unit."""
    inp = state.get("input") or {}
    requested_load = inp.get("load", 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:power_on_self_test"],
        "battery_level": 98.5 - (requested_load * 0.5),
        "sensor_calibration": True,
        "actuator_status": "idle",
    }


def process_actuation(state: State) -> dict[str, Any]:
    """Simulate robotics task execution and motion control."""
    battery = state.get("battery_level", 0.0)
    calibrated = state.get("sensor_calibration", False)

    if battery > 10.0 and calibrated:
        status = "executed_successfully"
        consumption = 5.2
    else:
        status = "insufficient_power_or_calibration"
        consumption = 0.1

    return {
        "log": [f"{UNISPSC_CODE}:process_actuation"],
        "battery_level": battery - consumption,
        "actuator_status": status,
        "telemetry_data": {
            "position": {"x": 10.5, "y": 20.2, "z": 0.0},
            "velocity": 0.0,
            "error_code": 0 if status == "executed_successfully" else 1,
        }
    }


def telemeter_output(state: State) -> dict[str, Any]:
    """Package robotic state and telemetry into the final result."""
    return {
        "log": [f"{UNISPSC_CODE}:telemeter_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": state.get("actuator_status"),
            "remaining_power": f"{state.get('battery_level'):.2f}%",
            "telemetry": state.get("telemetry_data"),
            "ok": state.get("actuator_status") == "executed_successfully",
        },
    }


_g = StateGraph(State)
_g.add_node("power_on_self_test", power_on_self_test)
_g.add_node("process_actuation", process_actuation)
_g.add_node("telemeter_output", telemeter_output)

_g.add_edge(START, "power_on_self_test")
_g.add_edge("power_on_self_test", "process_actuation")
_g.add_edge("process_actuation", "telemeter_output")
_g.add_edge("telemeter_output", END)

graph = _g.compile()
