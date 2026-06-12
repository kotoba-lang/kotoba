# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231902 — Laser (segment 23).
Bespoke logic for industrial laser equipment lifecycle and operation state management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231902"
UNISPSC_TITLE = "Laser"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231902"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for "Laser"
    safety_interlock_engaged: bool
    beam_intensity_mw: float
    cooling_system_active: bool
    pulse_frequency_hz: int


def check_safety(state: State) -> dict[str, Any]:
    """Verify safety interlocks and cooling systems before activation."""
    inp = state.get("input") or {}
    interlock = inp.get("interlock", True)
    cooling = inp.get("cooling", True)
    return {
        "log": [f"{UNISPSC_CODE}:check_safety"],
        "safety_interlock_engaged": interlock,
        "cooling_system_active": cooling,
    }


def configure_optics(state: State) -> dict[str, Any]:
    """Configure beam intensity and pulse frequency based on input parameters."""
    inp = state.get("input") or {}
    intensity = float(inp.get("target_mw", 500.0))
    frequency = int(inp.get("frequency_hz", 1000))

    # Safety throttle if cooling is insufficient
    if not state.get("cooling_system_active"):
        intensity = min(intensity, 10.0)

    return {
        "log": [f"{UNISPSC_CODE}:configure_optics"],
        "beam_intensity_mw": intensity,
        "pulse_frequency_hz": frequency,
    }


def execute_laser_sequence(state: State) -> dict[str, Any]:
    """Finalize the laser operation sequence and produce result telemetry."""
    is_safe = state.get("safety_interlock_engaged") and state.get("cooling_system_active")

    return {
        "log": [f"{UNISPSC_CODE}:execute_laser_sequence"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational_status": "firing" if is_safe else "inhibited",
            "telemetry": {
                "intensity_mw": state.get("beam_intensity_mw"),
                "pulse_hz": state.get("pulse_frequency_hz"),
                "safety_ok": is_safe
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("check_safety", check_safety)
_g.add_node("configure_optics", configure_optics)
_g.add_node("execute_laser_sequence", execute_laser_sequence)

_g.add_edge(START, "check_safety")
_g.add_edge("check_safety", "configure_optics")
_g.add_edge("configure_optics", "execute_laser_sequence")
_g.add_edge("execute_laser_sequence", END)

graph = _g.compile()
