# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151512"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151512"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Actuator control
    duty_cycle: float
    target_extension_mm: float
    current_pressure_psi: float
    calibration_verified: bool
    fault_detected: bool


def pre_flight_check(state: State) -> dict[str, Any]:
    """Verify actuator calibration and system pressure before movement."""
    inp = state.get("input") or {}
    target = float(inp.get("extension", 0.0))
    pressure = float(inp.get("pressure", 90.0))

    # Simple validation logic
    is_valid = pressure > 40.0 and pressure < 120.0
    return {
        "log": [f"{UNISPSC_CODE}:pre_flight_check"],
        "target_extension_mm": target,
        "current_pressure_psi": pressure,
        "calibration_verified": is_valid,
        "fault_detected": not is_valid
    }


def execute_motion(state: State) -> dict[str, Any]:
    """Execute the actuator stroke and update internal telemetry."""
    if state.get("fault_detected"):
        return {"log": [f"{UNISPSC_CODE}:execute_motion_aborted"]}

    target = state.get("target_extension_mm", 0.0)
    # Simulate high duty cycle during mechanical stress
    return {
        "log": [f"{UNISPSC_CODE}:execute_motion_success"],
        "duty_cycle": 0.85,
        "current_pressure_psi": state.get("current_pressure_psi", 90.0) - 5.0
    }


def telemetry_report(state: State) -> dict[str, Any]:
    """Compile final actuator status and performance metrics."""
    ok = state.get("calibration_verified", False) and not state.get("fault_detected", False)

    return {
        "log": [f"{UNISPSC_CODE}:telemetry_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "OPERATIONAL" if ok else "FAULT",
            "extension_reached": state.get("target_extension_mm", 0.0),
            "ok": ok
        }
    }


_g = StateGraph(State)

_g.add_node("pre_flight", pre_flight_check)
_g.add_node("motion", execute_motion)
_g.add_node("report", telemetry_report)

_g.add_edge(START, "pre_flight")
_g.add_edge("pre_flight", "motion")
_g.add_edge("motion", "report")
_g.add_edge("report", END)

graph = _g.compile()
