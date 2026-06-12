# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172800 — Hydraulic (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172800"
UNISPSC_TITLE = "Hydraulic"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Hydraulic systems
    pressure_psi: int
    fluid_temp_celsius: float
    actuator_health: str
    cycle_count: int


def check_pressure(state: State) -> dict[str, Any]:
    """Validates system pressure against safe operating thresholds."""
    inp = state.get("input") or {}
    pressure = inp.get("pressure", 2800)

    return {
        "log": [f"{UNISPSC_CODE}:check_pressure"],
        "pressure_psi": pressure,
        "actuator_health": "Healthy" if pressure < 4000 else "Warning",
    }


def assess_fluid(state: State) -> dict[str, Any]:
    """Analyzes fluid temperature and determines maintenance urgency."""
    inp = state.get("input") or {}
    temp = inp.get("temperature", 55.0)

    return {
        "log": [f"{UNISPSC_CODE}:assess_fluid"],
        "fluid_temp_celsius": temp,
        "cycle_count": inp.get("cycles", 1200),
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Compiles hydraulic metrics into a standardized actor result."""
    pressure = state.get("pressure_psi", 0)
    health = state.get("actuator_health", "Unknown")
    temp = state.get("fluid_temp_celsius", 0.0)

    is_ok = health != "Warning" and temp < 85.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "pressure": pressure,
                "temperature": temp,
                "health": health,
                "cycles": state.get("cycle_count", 0),
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("check_pressure", check_pressure)
_g.add_node("assess_fluid", assess_fluid)
_g.add_node("finalize_telemetry", finalize_telemetry)

_g.add_edge(START, "check_pressure")
_g.add_edge("check_pressure", "assess_fluid")
_g.add_edge("assess_fluid", "finalize_telemetry")
_g.add_edge("finalize_telemetry", END)

graph = _g.compile()
