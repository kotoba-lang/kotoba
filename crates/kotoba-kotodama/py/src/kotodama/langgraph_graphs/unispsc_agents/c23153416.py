# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153416 — Laser (segment 23).
Bespoke logic for safety interlocking, optical calibration, and beam emission.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153416"
UNISPSC_TITLE = "Laser"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153416"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Laser domain state
    wavelength_nm: float
    power_watts: float
    interlock_status: str
    thermal_stability_verified: bool
    pulse_frequency_hz: float


def check_safety_interlocks(state: State) -> dict[str, Any]:
    """Verify that all safety interlocks are engaged and thermal limits are within range."""
    inp = state.get("input") or {}
    interlock = inp.get("interlock", "CLOSED")
    temp_c = inp.get("ambient_temp", 22.5)

    stability = 18.0 <= temp_c <= 28.0
    return {
        "log": [f"{UNISPSC_CODE}:check_safety_interlocks: interlock={interlock}, thermal={stability}"],
        "interlock_status": interlock,
        "thermal_stability_verified": stability,
    }


def calibrate_optics(state: State) -> dict[str, Any]:
    """Configure optical parameters based on session input."""
    inp = state.get("input") or {}
    # Default to 1064nm (Infrared) if not specified
    wavelength = float(inp.get("wavelength", 1064.0))
    power = float(inp.get("power", 15.5))
    freq = float(inp.get("frequency", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_optics: target={wavelength}nm, power={power}W"],
        "wavelength_nm": wavelength,
        "power_watts": power,
        "pulse_frequency_hz": freq,
    }


def fire_laser(state: State) -> dict[str, Any]:
    """Execute the laser pulse sequence if safety conditions are met."""
    safe = (
        state.get("interlock_status") == "CLOSED" and
        state.get("thermal_stability_verified", False)
    )

    if safe:
        status = "OPERATIONAL_EMISSION_SUCCESS"
        ok = True
    else:
        status = "EMISSION_ABORTED_SAFETY_VIOLATION"
        ok = False

    return {
        "log": [f"{UNISPSC_CODE}:fire_laser: {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "execution_status": status,
            "metrics": {
                "wavelength": state.get("wavelength_nm"),
                "power": state.get("power_watts"),
                "frequency": state.get("pulse_frequency_hz"),
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("check_safety_interlocks", check_safety_interlocks)
_g.add_node("calibrate_optics", calibrate_optics)
_g.add_node("fire_laser", fire_laser)

_g.add_edge(START, "check_safety_interlocks")
_g.add_edge("check_safety_interlocks", "calibrate_optics")
_g.add_edge("calibrate_optics", "fire_laser")
_g.add_edge("fire_laser", END)

graph = _g.compile()
