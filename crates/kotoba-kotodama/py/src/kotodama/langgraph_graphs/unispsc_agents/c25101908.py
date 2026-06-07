# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101908 — Quad (segment 25).

This bespoke agent manages the lifecycle of a Quad (ATV) commercial vehicle,
handling mechanical inspection, terrain-specific performance tuning, and
final dispatch preparation for commercial or utility use.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101908"
UNISPSC_TITLE = "Quad"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101908"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Quad vehicles
    chassis_serial: str
    inspection_status: str
    terrain_mode: str
    power_output_kw: float
    safety_compliance: bool


def validate_inspection(state: State) -> dict[str, Any]:
    """Validates the mechanical integrity and chassis serial of the quad."""
    inp = state.get("input") or {}
    serial = inp.get("serial", "Q-2510-908")
    passed = inp.get("mechanical_check", True)

    return {
        "log": [f"{UNISPSC_CODE}:validate_inspection: {serial}"],
        "chassis_serial": serial,
        "inspection_status": "PASSED" if passed else "FAILED",
        "safety_compliance": passed,
    }


def tune_performance(state: State) -> dict[str, Any]:
    """Sets the terrain mode and adjusts power output parameters."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "Utility")
    # Simulation of tuning logic
    power = 35.5 if mode == "Sport" else 22.0

    return {
        "log": [f"{UNISPSC_CODE}:tune_performance: {mode}"],
        "terrain_mode": mode,
        "power_output_kw": power,
    }


def prepare_dispatch(state: State) -> dict[str, Any]:
    """Prepares the final result and signs off on the vehicle dispatch."""
    is_ready = state.get("safety_compliance", False)

    return {
        "log": [f"{UNISPSC_CODE}:prepare_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "serial": state.get("chassis_serial"),
            "mode": state.get("terrain_mode"),
            "power": f"{state.get('power_output_kw')}kW",
            "ready_for_dispatch": is_ready,
            "ok": is_ready,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_inspection", validate_inspection)
_g.add_node("tune_performance", tune_performance)
_g.add_node("prepare_dispatch", prepare_dispatch)

_g.add_edge(START, "validate_inspection")
_g.add_edge("validate_inspection", "tune_performance")
_g.add_edge("tune_performance", "prepare_dispatch")
_g.add_edge("prepare_dispatch", END)

graph = _g.compile()
