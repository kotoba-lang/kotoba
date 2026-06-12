# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111805 — Tensioner.

Bespoke graph for managing mechanical tensioning operations, ensuring component
calibration and safety thresholds are maintained during system installation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111805"
UNISPSC_TITLE = "Tensioner"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111805"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific state for Tensioner
    target_tension_kn: float
    measured_tension_kn: float
    calibration_verified: bool
    safety_lock_engaged: bool
    load_capacity_kn: float


def inspect_tensioner(state: State) -> dict[str, Any]:
    """Validates input specifications against the tensioner's physical capacity."""
    inp = state.get("input") or {}
    target = float(inp.get("target_tension", 12.5))
    capacity = float(inp.get("max_capacity", 40.0))

    # Tensioner must not exceed its rated load capacity
    is_valid = target <= capacity

    return {
        "log": [f"{UNISPSC_CODE}:inspect_tensioner"],
        "target_tension_kn": target,
        "load_capacity_kn": capacity,
        "calibration_verified": is_valid
    }


def adjust_calibration(state: State) -> dict[str, Any]:
    """Simulates the adjustment of the tensioning mechanism to reach target value."""
    target = state.get("target_tension_kn", 0.0)
    # Simulate measurement with a small precision variance
    measured = target * 0.9995

    return {
        "log": [f"{UNISPSC_CODE}:adjust_calibration"],
        "measured_tension_kn": measured
    }


def secure_installation(state: State) -> dict[str, Any]:
    """Engages the safety locking mechanism and reports the final status."""
    verified = state.get("calibration_verified", False)
    measured = state.get("measured_tension_kn", 0.0)
    target = state.get("target_tension_kn", 0.0)

    # Define tolerance (0.5%)
    tolerance = 0.005
    within_tolerance = (abs(measured - target) / target < tolerance) if target > 0 else True
    is_secure = verified and within_tolerance

    return {
        "log": [f"{UNISPSC_CODE}:secure_installation"],
        "safety_lock_engaged": is_secure,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "final_reading_kn": measured,
            "status": "OPERATIONAL" if is_secure else "CALIBRATION_ERROR",
            "ok": is_secure,
        }
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_tensioner)
_g.add_node("adjust", adjust_calibration)
_g.add_node("secure", secure_installation)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "adjust")
_g.add_edge("adjust", "secure")
_g.add_edge("secure", END)

graph = _g.compile()
