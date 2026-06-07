# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174207 — Steering (segment 25).

Bespoke graph logic for vehicle steering component validation and calibration reporting.
This agent manages the inspection lifecycle for steering assemblies, rack integrity,
and safety certification parameters.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174207"
UNISPSC_TITLE = "Steering"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174207"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    rack_integrity_verified: bool
    steering_angle_offset: float
    power_assist_status: str
    safety_standard_met: bool


def inspect_steering_rack(state: State) -> dict[str, Any]:
    """Inspects the physical integrity of the steering rack and pinion assembly."""
    inp = state.get("input") or {}
    # Simulate a check for rack stress fractures or mounting bolt torque
    is_solid = inp.get("stress_test_passed", True)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_steering_rack"],
        "rack_integrity_verified": is_solid,
    }


def calibrate_alignment(state: State) -> dict[str, Any]:
    """Calibrates the steering angle sensors and checks power assist fluid levels."""
    inp = state.get("input") or {}
    offset = inp.get("raw_offset", 0.0) / 2.0
    assist = "OPTIMAL" if inp.get("fluid_pressure", 100) > 80 else "LOW_PRESSURE"

    # We meet safety standards only if rack is verified and offset is minimal
    integrity = state.get("rack_integrity_verified", False)
    safe = integrity and abs(offset) < 0.5

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_alignment"],
        "steering_angle_offset": offset,
        "power_assist_status": assist,
        "safety_standard_met": safe,
    }


def emit_compliance_report(state: State) -> dict[str, Any]:
    """Finalizes the steering assembly report for segment 25 compliance."""
    is_safe = state.get("safety_standard_met", False)
    assist = state.get("power_assist_status", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:emit_compliance_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_safe,
            "diagnostics": {
                "assist_mode": assist,
                "angle_correction": state.get("steering_angle_offset", 0.0),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_steering_rack)
_g.add_node("calibrate", calibrate_alignment)
_g.add_node("emit", emit_compliance_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calibrate")
_g.add_edge("calibrate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
