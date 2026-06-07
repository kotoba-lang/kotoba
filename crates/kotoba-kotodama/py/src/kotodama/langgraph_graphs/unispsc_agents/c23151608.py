# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151608 — Robot (segment 23).

This bespoke LangGraph agent manages the state and telemetry for a robotic unit,
handling power-on self-tests, actuator calibration, and operational reporting.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151608"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151608"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    battery_charge: float
    proximity_alert: bool
    joint_calibration: str
    target_load: float


def power_on_self_test(state: State) -> dict[str, Any]:
    """Initializes the robotic unit and verifies power levels."""
    inp = state.get("input") or {}
    charge = inp.get("charge_level", 100.0)
    load = inp.get("load_kg", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:power_on_self_test"],
        "battery_charge": charge,
        "target_load": load,
        "proximity_alert": False,
    }


def calibrate_actuators(state: State) -> dict[str, Any]:
    """Performs joint calibration based on the current load."""
    load = state.get("target_load", 0.0)
    calibration = "standard" if load < 50.0 else "heavy_duty"

    # Simulate a proximity check during movement
    has_alert = load > 200.0

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_actuators"],
        "joint_calibration": f"{calibration}_mode_active",
        "proximity_alert": has_alert,
    }


def generate_robot_report(state: State) -> dict[str, Any]:
    """Generates the final telemetry and operational status report."""
    is_safe = not state.get("proximity_alert", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_robot_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "battery": state.get("battery_charge"),
                "calibration": state.get("joint_calibration"),
                "safe_operation": is_safe,
            },
            "ok": is_safe and state.get("battery_charge", 0) > 10,
        },
    }


_g = StateGraph(State)

_g.add_node("power_on_self_test", power_on_self_test)
_g.add_node("calibrate_actuators", calibrate_actuators)
_g.add_node("generate_robot_report", generate_robot_report)

_g.add_edge(START, "power_on_self_test")
_g.add_edge("power_on_self_test", "calibrate_actuators")
_g.add_edge("calibrate_actuators", "generate_robot_report")
_g.add_edge("generate_robot_report", END)

graph = _g.compile()
