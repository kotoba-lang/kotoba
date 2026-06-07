# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21111500 — Tiller.
Bespoke logic for agricultural soil preparation machinery.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21111500"
UNISPSC_TITLE = "Tiller"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21111500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Tiller operation
    soil_density: str
    target_depth_mm: int
    blade_integrity: float
    safety_check_passed: bool


def inspect_machinery(state: State) -> dict[str, Any]:
    """Node to verify tiller mechanical status and safety protocols."""
    inp = state.get("input") or {}
    # Simulate a mechanical inspection based on provided telemetry
    integrity = inp.get("blade_wear", 0.98)
    fuel = inp.get("fuel_level", 1.0)
    passed = integrity > 0.4 and fuel > 0.1

    return {
        "log": [f"{UNISPSC_CODE}:inspect_machinery"],
        "blade_integrity": integrity,
        "safety_check_passed": passed,
    }


def calibrate_settings(state: State) -> dict[str, Any]:
    """Node to determine optimal tilling depth based on soil density."""
    inp = state.get("input") or {}
    density = inp.get("soil_type", "medium-loam")

    # Heuristic logic for agricultural soil preparation
    depth = 150  # default mm
    if density == "compacted-clay":
        depth = 220
    elif density == "loose-sand":
        depth = 110

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_settings"],
        "soil_density": density,
        "target_depth_mm": depth,
    }


def execute_tilling(state: State) -> dict[str, Any]:
    """Node to finalize the tilling operation and emit performance metrics."""
    success = state.get("safety_check_passed", False)
    depth = state.get("target_depth_mm", 0)
    integrity = state.get("blade_integrity", 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:execute_tilling"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation_successful": success,
            "final_depth_attained_mm": depth if success else 0,
            "blade_health_report": "nominal" if integrity > 0.7 else "inspect-required",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_machinery", inspect_machinery)
_g.add_node("calibrate_settings", calibrate_settings)
_g.add_node("execute_tilling", execute_tilling)

_g.add_edge(START, "inspect_machinery")
_g.add_edge("inspect_machinery", "calibrate_settings")
_g.add_edge("calibrate_settings", "execute_tilling")
_g.add_edge("execute_tilling", END)

graph = _g.compile()
