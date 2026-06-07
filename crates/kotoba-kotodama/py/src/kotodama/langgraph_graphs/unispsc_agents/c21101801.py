# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101801 — Mower (segment 21).

Bespoke graph for Mower operations, managing equipment state, safety
verification, and maintenance tracking during vegetation control tasks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101801"
UNISPSC_TITLE = "Mower"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Mower operations
    cutting_height_mm: int
    blade_integrity_score: float
    fuel_level_percent: float
    safety_interlock_status: bool


def inspect_mower(state: State) -> dict[str, Any]:
    """Node: Perform pre-operational check on the mower hardware."""
    inp = state.get("input") or {}

    # Initialize mower metrics from input or defaults
    height = inp.get("target_height_mm", 45)
    fuel = inp.get("current_fuel", 100.0)
    blades = inp.get("current_blades", 98.5)

    # Simple logic for safety interlock
    safety_ok = fuel > 5.0 and blades > 40.0

    return {
        "log": [f"{UNISPSC_CODE}:inspect_mower"],
        "cutting_height_mm": height,
        "fuel_level_percent": fuel,
        "blade_integrity_score": blades,
        "safety_interlock_status": safety_ok,
    }


def perform_mowing(state: State) -> dict[str, Any]:
    """Node: Simulate the mowing process and resource depletion."""
    if not state.get("safety_interlock_status"):
        return {"log": [f"{UNISPSC_CODE}:perform_mowing:aborted_safety_failure"]}

    current_fuel = state.get("fuel_level_percent", 0.0)
    current_blades = state.get("blade_integrity_score", 0.0)

    # Update state based on work performed
    return {
        "log": [f"{UNISPSC_CODE}:perform_mowing:completed_successfully"],
        "fuel_level_percent": max(0.0, current_fuel - 22.5),
        "blade_integrity_score": max(0.0, current_blades - 1.5),
    }


def report_and_shutdown(state: State) -> dict[str, Any]:
    """Node: Finalize the state and emit the operation summary."""
    success = state.get("safety_interlock_status", False)

    return {
        "log": [f"{UNISPSC_CODE}:report_and_shutdown"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation_successful": success,
            "telemetry": {
                "remaining_fuel": state.get("fuel_level_percent"),
                "blade_wear": state.get("blade_integrity_score"),
                "height_setting": state.get("cutting_height_mm")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_mower)
_g.add_node("mow", perform_mowing)
_g.add_node("shutdown", report_and_shutdown)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "mow")
_g.add_edge("mow", "shutdown")
_g.add_edge("shutdown", END)

graph = _g.compile()
