# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101704 — Laser (segment 22).

Bespoke graph logic for laser equipment management, handling safety
verification, beam calibration, and operational status reporting.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101704"
UNISPSC_TITLE = "Laser"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Extra domain fields for "Laser"
    beam_wavelength_nm: float
    pulse_frequency_hz: float
    safety_interlock_active: bool
    calibration_status: str
    thermal_load_percent: float


def validate_safety(state: State) -> dict[str, Any]:
    """Ensures safety protocols are active before operation."""
    inp = state.get("input") or {}
    interlock = inp.get("safety_interlock", True)
    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "safety_interlock_active": interlock,
        "thermal_load_percent": 15.5,
    }


def calibrate_beam(state: State) -> dict[str, Any]:
    """Calculates beam parameters and calibration offsets."""
    inp = state.get("input") or {}
    wavelength = inp.get("wavelength", 1064.0)
    frequency = inp.get("frequency", 50.0)

    status = "CALIBRATED" if state.get("safety_interlock_active") else "FAILED_UNSAFE"

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_beam"],
        "beam_wavelength_nm": wavelength,
        "pulse_frequency_hz": frequency,
        "calibration_status": status,
    }


def finalize_operation(state: State) -> dict[str, Any]:
    """Produces the final diagnostic and operational record."""
    is_ok = state.get("calibration_status") == "CALIBRATED"
    return {
        "log": [f"{UNISPSC_CODE}:finalize_operation"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation_valid": is_ok,
            "metrics": {
                "wavelength": state.get("beam_wavelength_nm"),
                "frequency": state.get("pulse_frequency_hz"),
                "thermal_load": state.get("thermal_load_percent"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("validate_safety", validate_safety)
_g.add_node("calibrate_beam", calibrate_beam)
_g.add_node("finalize_operation", finalize_operation)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "calibrate_beam")
_g.add_edge("calibrate_beam", "finalize_operation")
_g.add_edge("finalize_operation", END)

graph = _g.compile()
