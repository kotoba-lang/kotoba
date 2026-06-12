# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122333 — Actuator (segment 20).

Bespoke graph logic for mechanical/electrical actuator control simulation.
This agent handles signal processing, torque calculation, and stroke execution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122333"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122333"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Actuator
    signal_voltage: float
    target_position: int
    is_engaged: bool
    torque_nm: float
    error_code: int


def initialize_actuator(state: State) -> dict[str, Any]:
    """Validates input signal and initializes hardware state."""
    inp = state.get("input") or {}
    target = int(inp.get("position", 0))
    return {
        "log": [f"{UNISPSC_CODE}:initialize_actuator"],
        "target_position": target,
        "is_engaged": True,
        "error_code": 0,
    }


def calculate_dynamics(state: State) -> dict[str, Any]:
    """Computes necessary torque and signal voltage for the movement."""
    target = state.get("target_position", 0)
    # Simple linear approximation: 0.2Nm per unit of position
    calculated_torque = abs(target) * 0.2
    # Voltage scaling (e.g. 0-10V range)
    voltage = min(10.0, calculated_torque * 0.5)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_dynamics"],
        "torque_nm": calculated_torque,
        "signal_voltage": voltage,
    }


def perform_stroke(state: State) -> dict[str, Any]:
    """Simulates the physical movement and generates the final response."""
    voltage = state.get("signal_voltage", 0.0)
    torque = state.get("torque_nm", 0.0)
    target = state.get("target_position", 0)

    return {
        "log": [f"{UNISPSC_CODE}:perform_stroke"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "engaged",
            "telemetry": {
                "voltage_applied": f"{voltage}V",
                "torque_peak": f"{torque}Nm",
                "final_position": target
            },
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize_actuator", initialize_actuator)
_g.add_node("calculate_dynamics", calculate_dynamics)
_g.add_node("perform_stroke", perform_stroke)

_g.add_edge(START, "initialize_actuator")
_g.add_edge("initialize_actuator", "calculate_dynamics")
_g.add_edge("calculate_dynamics", "perform_stroke")
_g.add_edge("perform_stroke", END)

graph = _g.compile()
