# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251507"
UNISPSC_TITLE = "Bender"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    bend_angle_deg: float
    material_thickness: float
    clamping_force_tons: float
    cycle_time_sec: float


def inspect_metal_spec(state: State) -> dict[str, Any]:
    """Validates the metal bending specifications from the input work order."""
    inp = state.get("input") or {}
    angle = inp.get("angle", 90.0)
    thickness = inp.get("thickness", 0.05)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_metal_spec thickness={thickness}mm"],
        "bend_angle_deg": float(angle),
        "material_thickness": float(thickness),
    }


def calculate_bending_force(state: State) -> dict[str, Any]:
    """Calculates the hydraulic force required for the specific metal gauge."""
    thickness = state.get("material_thickness", 0.0)
    # Simple physical simulation: Force required scales with thickness squared
    required_force = (thickness ** 2) * 50.0
    return {
        "log": [f"{UNISPSC_CODE}:calculate_bending_force required={required_force:.2f} tons"],
        "clamping_force_tons": required_force,
    }


def perform_bend_operation(state: State) -> dict[str, Any]:
    """Simulates the physical metal bending cycle on the machine."""
    angle = state.get("bend_angle_deg", 0.0)
    # Simulate variable cycle time based on bend complexity
    processing_time = 1.2 + (angle / 180.0)
    return {
        "log": [f"{UNISPSC_CODE}:perform_bend_operation angle={angle} degrees"],
        "cycle_time_sec": processing_time,
    }


def generate_bender_telemetry(state: State) -> dict[str, Any]:
    """Emits the final telemetry and operational status for the production run."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_bender_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "force_applied_tons": state.get("clamping_force_tons"),
                "cycle_duration_sec": state.get("cycle_time_sec"),
                "achieved_angle": state.get("bend_angle_deg"),
            },
            "status": "BENDING_COMPLETE",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_metal_spec)
_g.add_node("calculate", calculate_bending_force)
_g.add_node("bend", perform_bend_operation)
_g.add_node("telemetry", generate_bender_telemetry)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calculate")
_g.add_edge("calculate", "bend")
_g.add_edge("bend", "telemetry")
_g.add_edge("telemetry", END)

graph = _g.compile()
