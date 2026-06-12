# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142501 — Drill (segment 20).

Bespoke graph logic for mechanical drilling operations, including safety
verification, parameter optimization, and execution monitoring for mining
and well-drilling machinery.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142501"
UNISPSC_TITLE = "Drill"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Well Drilling Machinery
    drill_bit_type: str
    target_depth_meters: float
    rotational_speed_rpm: int
    hydraulic_pressure_psi: float
    safety_check_passed: bool


def verify_safety(state: State) -> dict[str, Any]:
    """Validates the mechanical integrity and safety interlocks of the drill."""
    inp = state.get("input") or {}
    # Simulate a safety verification process
    pressure = float(inp.get("initial_pressure", 2500.0))
    passed = pressure > 1000.0 and pressure < 5000.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "hydraulic_pressure_psi": pressure,
        "safety_check_passed": passed
    }


def optimize_parameters(state: State) -> dict[str, Any]:
    """Configures drilling parameters based on the specific material and bit type."""
    inp = state.get("input") or {}
    bit_type = inp.get("bit_type", "Tricone")
    depth = float(inp.get("depth", 500.0))

    # Calculate RPM based on bit type (simulated logic)
    rpm = 120 if bit_type == "PDC" else 80

    return {
        "log": [f"{UNISPSC_CODE}:optimize_parameters"],
        "drill_bit_type": bit_type,
        "target_depth_meters": depth,
        "rotational_speed_rpm": rpm
    }


def initiate_drilling(state: State) -> dict[str, Any]:
    """Finalizes the operational plan and emits the machine state report."""
    is_safe = state.get("safety_check_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:initiate_drilling"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation_status": "READY" if is_safe else "LOCKED",
            "parameters": {
                "bit": state.get("drill_bit_type"),
                "depth": state.get("target_depth_meters"),
                "rpm": state.get("rotational_speed_rpm"),
                "pressure": state.get("hydraulic_pressure_psi")
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_safety", verify_safety)
_g.add_node("optimize_parameters", optimize_parameters)
_g.add_node("initiate_drilling", initiate_drilling)

_g.add_edge(START, "verify_safety")
_g.add_edge("verify_safety", "optimize_parameters")
_g.add_edge("optimize_parameters", "initiate_drilling")
_g.add_edge("initiate_drilling", END)

graph = _g.compile()
