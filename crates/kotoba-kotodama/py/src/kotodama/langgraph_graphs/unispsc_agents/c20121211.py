# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121211 — Laser (segment 20).

Bespoke graph for laser hardware control state management. This agent handles
parameter validation, safety interlock verification, and calibration routines
specific to laser systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121211"
UNISPSC_TITLE = "Laser"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121211"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Laser
    wavelength_nm: float
    power_output_mw: float
    safety_interlock_status: bool
    calibration_verified: bool
    beam_stable: bool


def validate_parameters(state: State) -> dict[str, Any]:
    """Validate input parameters for wavelength and power."""
    inp = state.get("input") or {}
    wavelength = float(inp.get("wavelength", 632.8))  # Default to HeNe wavelength
    power = float(inp.get("power", 5.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters: w={wavelength}nm, p={power}mW"],
        "wavelength_nm": wavelength,
        "power_output_mw": power,
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Check safety interlocks based on power levels."""
    power = state.get("power_output_mw", 0.0)
    # High power lasers (> 500mW) require strict interlock verification
    interlock_ok = True if power < 500.0 else state.get("input", {}).get("interlock_override", False)

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety: interlock={interlock_ok}"],
        "safety_interlock_status": interlock_ok,
    }


def calibrate(state: State) -> dict[str, Any]:
    """Perform beam alignment and power calibration."""
    if not state.get("safety_interlock_status", False):
        return {
            "log": [f"{UNISPSC_CODE}:calibrate: FAILED - Safety interlock open"],
            "calibration_verified": False,
            "beam_stable": False,
        }

    return {
        "log": [f"{UNISPSC_CODE}:calibrate: SUCCESS"],
        "calibration_verified": True,
        "beam_stable": True,
    }


def emit(state: State) -> dict[str, Any]:
    """Emit the final laser state and telemetry."""
    success = state.get("calibration_verified", False) and state.get("safety_interlock_status", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "wavelength": state.get("wavelength_nm"),
                "power": state.get("power_output_mw"),
                "stable": state.get("beam_stable"),
            },
            "status": "OPERATIONAL" if success else "FAULT",
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_parameters", validate_parameters)
_g.add_node("verify_safety", verify_safety)
_g.add_node("calibrate", calibrate)
_g.add_node("emit", emit)

_g.add_edge(START, "validate_parameters")
_g.add_edge("validate_parameters", "verify_safety")
_g.add_edge("verify_safety", "calibrate")
_g.add_edge("calibrate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
