# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101519 — Laser (segment 22).

This bespoke LangGraph agent manages operational parameters for laser systems,
including power configuration, safety envelope verification, and emission telemetry.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101519"
UNISPSC_TITLE = "Laser"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101519"


class State(TypedDict, total=False):
    # Required core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Bespoke domain fields for Laser
    power_mw: int
    wavelength_nm: float
    shutter_status: str
    thermal_load_percent: float
    safety_interlock_active: bool


def initialize_source(state: State) -> dict[str, Any]:
    """Sets requested beam parameters from input."""
    inp = state.get("input") or {}
    power = inp.get("requested_power", 50)  # Default to 50mW
    wavelength = inp.get("requested_wavelength", 632.8)  # HeNe default

    return {
        "log": [f"{UNISPSC_CODE}:initialize_source"],
        "power_mw": power,
        "wavelength_nm": wavelength,
        "shutter_status": "locked",
    }


def verify_safety_envelope(state: State) -> dict[str, Any]:
    """Checks safety constraints and cooling requirements."""
    p = state.get("power_mw", 0)

    # Simulate hardware checks
    interlock = True
    thermal = 15.0 + (p * 0.05)  # Linear heat approximation

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_envelope"],
        "safety_interlock_active": interlock,
        "thermal_load_percent": min(thermal, 100.0),
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Prepares the final operational report."""
    is_safe = state.get("safety_interlock_active") and state.get("thermal_load_percent") < 90.0
    status = "READY" if is_safe else "INHIBITED"

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "operational_status": status,
        "metrics": {
            "p": state.get("power_mw"),
            "w": state.get("wavelength_nm"),
            "thermal": f"{state.get('thermal_load_percent'):.1f}%",
            "shutter": "OPEN" if is_safe else "CLOSED"
        },
        "ok": is_safe
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "shutter_status": "open" if is_safe else "closed",
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("initialize_source", initialize_source)
_g.add_node("verify_safety_envelope", verify_safety_envelope)
_g.add_node("finalize_telemetry", finalize_telemetry)

_g.add_edge(START, "initialize_source")
_g.add_edge("initialize_source", "verify_safety_envelope")
_g.add_edge("verify_safety_envelope", "finalize_telemetry")
_g.add_edge("finalize_telemetry", END)

graph = _g.compile()
