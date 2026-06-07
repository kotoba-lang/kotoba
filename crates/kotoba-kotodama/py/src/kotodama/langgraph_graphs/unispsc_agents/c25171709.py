# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171709 — Brake (segment 25).

Bespoke LangGraph implementation for braking system inspection and safety
certification. This agent processes hydraulic pressure, pad wear, and
thermal data to determine component integrity and service status.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171709"
UNISPSC_TITLE = "Brake"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171709"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Brake system
    hydraulic_pressure_psi: float
    pad_wear_percentage: float
    temperature_celsius: float
    integrity_check_passed: bool
    safety_rating: str


def inspect_brake_hardware(state: State) -> dict[str, Any]:
    """Initializes domain state from input parameters."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 1000.0))
    wear = float(inp.get("wear", 15.0))
    temp = float(inp.get("temp", 35.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_brake_hardware"],
        "hydraulic_pressure_psi": pressure,
        "pad_wear_percentage": wear,
        "temperature_celsius": temp,
    }


def evaluate_braking_efficiency(state: State) -> dict[str, Any]:
    """Calculates safety thresholds and system integrity."""
    pressure = state.get("hydraulic_pressure_psi", 0.0)
    wear = state.get("pad_wear_percentage", 0.0)
    temp = state.get("temperature_celsius", 0.0)

    # Safety thresholds:
    # Minimum pressure: 800 PSI, Max wear: 85%, Max operating temp: 450C
    is_safe_pressure = pressure >= 800.0
    is_safe_wear = wear <= 85.0
    is_safe_temp = temp <= 450.0

    passed = is_safe_pressure and is_safe_wear and is_safe_temp

    rating = "CRITICAL_FAILURE"
    if passed:
        if wear < 20.0 and temp < 100.0:
            rating = "OPTIMAL"
        elif wear < 60.0:
            rating = "NOMINAL"
        else:
            rating = "MAINTENANCE_REQUIRED"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_braking_efficiency"],
        "integrity_check_passed": passed,
        "safety_rating": rating,
    }


def certify_brake_system(state: State) -> dict[str, Any]:
    """Finalizes the inspection result for the UnispscAgentExecutorCell."""
    passed = state.get("integrity_check_passed", False)
    rating = state.get("safety_rating", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:certify_brake_system"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "integrity_passed": passed,
            "safety_rating": rating,
            "status": "APPROVED" if passed else "REJECTED",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_brake_hardware)
_g.add_node("evaluate", evaluate_braking_efficiency)
_g.add_node("certify", certify_brake_system)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "evaluate")
_g.add_edge("evaluate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
