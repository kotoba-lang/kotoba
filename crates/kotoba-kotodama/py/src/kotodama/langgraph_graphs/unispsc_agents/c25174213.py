# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174213 — Steering.

Bespoke LangGraph implementation for vehicle steering systems validation,
alignment calibration, and hydraulic integrity assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174213"
UNISPSC_TITLE = "Steering"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174213"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific steering fields
    hydraulic_integrity: bool
    linkage_clearance_mm: float
    torque_sensor_calibration: str
    column_locking_status: bool


def validate_hydraulic_system(state: State) -> dict[str, Any]:
    """Inspects steering fluid levels and pump pressure telemetry."""
    inp = state.get("input") or {}
    pressure = inp.get("psi_reading", 0)
    # Standard steering systems typically operate between 1100-1500 PSI
    is_safe = 1000 <= pressure <= 1600
    return {
        "log": [f"{UNISPSC_CODE}:validate_hydraulic_system"],
        "hydraulic_integrity": is_safe,
    }


def calibrate_steering_linkage(state: State) -> dict[str, Any]:
    """Adjusts tie-rod and rack-and-pinion geometry offsets."""
    inp = state.get("input") or {}
    raw_clearance = inp.get("measured_clearance", 2.5)
    # Correction logic: normalize to target 2.0mm
    target = 2.0
    adjustment = target - raw_clearance
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_steering_linkage"],
        "linkage_clearance_mm": target,
        "torque_sensor_calibration": "OPTIMIZED" if abs(adjustment) < 1.0 else "REQUIRES_RESET",
    }


def certify_steering_response(state: State) -> dict[str, Any]:
    """Final certification of the steering assembly and output generation."""
    integrity = state.get("hydraulic_integrity", False)
    calib = state.get("torque_sensor_calibration", "UNKNOWN")

    operational = integrity and calib == "OPTIMIZED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_steering_response"],
        "column_locking_status": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "safety_cert": operational,
            "diagnostics": {
                "clearance": state.get("linkage_clearance_mm"),
                "calibration": calib,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_hydraulic_system)
_g.add_node("calibrate", calibrate_steering_linkage)
_g.add_node("certify", certify_steering_response)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calibrate")
_g.add_edge("calibrate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
