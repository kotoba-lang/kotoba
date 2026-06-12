# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251504 — Bender (segment 23).

Bespoke LangGraph implementation for industrial bending machinery control logic.
This agent handles safety validation, pressure calculation based on material
specifications, and execution simulation for precision bending operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251504"
UNISPSC_TITLE = "Bender"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251504"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for "Bender"
    bend_angle: float
    material_gauge: float
    clamping_pressure_psi: float
    safety_interlock_active: bool
    calibration_offset: float


def validate_safety(state: State) -> dict[str, Any]:
    """Ensures the bending machine is in a safe state for operation."""
    inp = state.get("input") or {}
    # Simulate hardware interlock check
    interlock = inp.get("safety_override") is not True
    return {
        "log": [f"{UNISPSC_CODE}:validate_safety -> active={interlock}"],
        "safety_interlock_active": interlock,
        "calibration_offset": 0.002,  # Simulated machine calibration
    }


def calculate_bend_parameters(state: State) -> dict[str, Any]:
    """Calculates required pressure and angle adjustments based on material."""
    if not state.get("safety_interlock_active"):
        return {"log": [f"{UNISPSC_CODE}:calculate_bend_parameters -> ABORTED (Safety)"]}

    inp = state.get("input") or {}
    target_angle = float(inp.get("angle", 90.0))
    gauge = float(inp.get("gauge", 0.125))

    # Simple logic: pressure proportional to gauge and angle
    required_psi = (target_angle / 10.0) * (gauge * 1000.0)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_bend_parameters -> psi={required_psi:.2f}"],
        "bend_angle": target_angle,
        "material_gauge": gauge,
        "clamping_pressure_psi": required_psi,
    }


def execute_bend(state: State) -> dict[str, Any]:
    """Simulates the physical bending operation and records the result."""
    if not state.get("safety_interlock_active"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_bend -> FAILED"],
            "result": {"ok": False, "error": "Safety interlock violation"}
        }

    angle = state.get("bend_angle", 0.0)
    pressure = state.get("clamping_pressure_psi", 0.0)
    offset = state.get("calibration_offset", 0.0)

    final_angle = angle + offset

    return {
        "log": [f"{UNISPSC_CODE}:execute_bend -> final_angle={final_angle}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "operation": "bend",
            "measured_angle": final_angle,
            "applied_pressure_psi": pressure,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_safety", validate_safety)
_g.add_node("calculate_bend_parameters", calculate_bend_parameters)
_g.add_node("execute_bend", execute_bend)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "calculate_bend_parameters")
_g.add_edge("calculate_bend_parameters", "execute_bend")
_g.add_edge("execute_bend", END)

graph = _g.compile()
