# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101202 — Motor (segment 26).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101202"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101202"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Motor component
    rated_voltage: float
    operating_rpm: int
    torque_output: float
    thermal_rating: str
    is_certified: bool


def inspect_electrical_specs(state: State) -> dict[str, Any]:
    """Node: Validate electrical input parameters for the motor unit."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 230.0))
    rpm = int(inp.get("rpm", 1750))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_electrical_specs"],
        "rated_voltage": voltage,
        "operating_rpm": rpm,
        "thermal_rating": "Class F",
    }


def compute_mechanical_dynamics(state: State) -> dict[str, Any]:
    """Node: Calculate mechanical performance metrics based on electrical specs."""
    rpm = state.get("operating_rpm", 1750)
    # Approximate torque (Nm) for a generic 5kW motor model
    # T = (P * 60) / (2 * pi * n)
    power_watts = 5000.0
    torque = (power_watts * 60) / (2 * 3.14159 * rpm) if rpm > 0 else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:compute_mechanical_dynamics"],
        "torque_output": round(torque, 2),
        "is_certified": rpm > 0 and state.get("rated_voltage", 0) > 0,
    }


def emit_compliance_report(state: State) -> dict[str, Any]:
    """Node: Compile specifications into the final actor result payload."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_compliance_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "voltage_v": state.get("rated_voltage"),
                "rpm": state.get("operating_rpm"),
                "torque_nm": state.get("torque_output"),
                "insulation": state.get("thermal_rating"),
            },
            "status": "operational" if state.get("is_certified") else "fault",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_electrical_specs", inspect_electrical_specs)
_g.add_node("compute_mechanical_dynamics", compute_mechanical_dynamics)
_g.add_node("emit_compliance_report", emit_compliance_report)

_g.add_edge(START, "inspect_electrical_specs")
_g.add_edge("inspect_electrical_specs", "compute_mechanical_dynamics")
_g.add_edge("compute_mechanical_dynamics", "emit_compliance_report")
_g.add_edge("emit_compliance_report", END)

graph = _g.compile()
