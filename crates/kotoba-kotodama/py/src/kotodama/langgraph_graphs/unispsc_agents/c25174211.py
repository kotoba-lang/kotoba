# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174211 — Steering.

Bespoke logic for steering system components, focusing on alignment calibration,
torque verification of linkages, and hydraulic/electronic pressure checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174211"
UNISPSC_TITLE = "Steering"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174211"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    alignment_angle_deg: float
    linkage_integrity_verified: bool
    fluid_pressure_psi: float
    calibration_offset: float


def inspect_hardware(state: State) -> dict[str, Any]:
    """Inspects the mechanical linkage and physical steering components."""
    inp = state.get("input") or {}
    # Simulate hardware diagnostic from input or defaults
    angle = inp.get("angle", 0.0)
    integrity = inp.get("integrity_check", True)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_hardware"],
        "alignment_angle_deg": float(angle),
        "linkage_integrity_verified": bool(integrity),
    }


def calibrate_steering_sensor(state: State) -> dict[str, Any]:
    """Calibrates the electronic steering sensors based on alignment data."""
    angle = state.get("alignment_angle_deg", 0.0)
    # Calculate offset based on deviation from zero
    offset = -angle * 0.05
    pressure = 1450.0 if state.get("linkage_integrity_verified") else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_steering_sensor"],
        "calibration_offset": offset,
        "fluid_pressure_psi": pressure,
    }


def validate_system_safety(state: State) -> dict[str, Any]:
    """Performs a final safety check on the steering system before emission."""
    pressure = state.get("fluid_pressure_psi", 0.0)
    integrity = state.get("linkage_integrity_verified", False)
    is_safe = pressure >= 1200.0 and integrity

    return {
        "log": [f"{UNISPSC_CODE}:validate_system_safety"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "system_status": "certified" if is_safe else "fault_detected",
            "metrics": {
                "offset": state.get("calibration_offset"),
                "pressure": pressure,
                "angle": state.get("alignment_angle_deg")
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_hardware", inspect_hardware)
_g.add_node("calibrate_steering_sensor", calibrate_steering_sensor)
_g.add_node("validate_system_safety", validate_system_safety)

_g.add_edge(START, "inspect_hardware")
_g.add_edge("inspect_hardware", "calibrate_steering_sensor")
_g.add_edge("calibrate_steering_sensor", "validate_system_safety")
_g.add_edge("validate_system_safety", END)

graph = _g.compile()
