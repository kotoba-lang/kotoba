# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101606 — Hole diggers (segment 21).

Bespoke graph logic for agricultural hole digging equipment operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101606"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Hole Diggers machinery
    auger_diameter_mm: int
    target_depth_mm: int
    safety_check_passed: bool
    calibration_offset: float


def validate_parameters(state: State) -> dict[str, Any]:
    """Inspects input for hole digging parameters."""
    inp = state.get("input") or {}
    diameter = inp.get("diameter", 300)
    depth = inp.get("depth", 1000)

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "auger_diameter_mm": diameter,
        "target_depth_mm": depth,
    }


def run_safety_diagnostic(state: State) -> dict[str, Any]:
    """Runs diagnostics on the hole digger safety systems."""
    diameter = state.get("auger_diameter_mm", 0)
    depth = state.get("target_depth_mm", 0)

    # Simple heuristic: extreme depth or diameter requires manual override
    is_safe = (diameter <= 1200) and (depth <= 3000)

    return {
        "log": [f"{UNISPSC_CODE}:run_safety_diagnostic"],
        "safety_check_passed": is_safe,
        "calibration_offset": 0.05 if is_safe else 0.0,
    }


def compile_operation_plan(state: State) -> dict[str, Any]:
    """Compiles the final operation plan for the agricultural machinery."""
    is_safe = state.get("safety_check_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:compile_operation_plan"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_safe,
            "operation": "HOLE_DIGGING",
            "spec_verified": {
                "diameter": state.get("auger_diameter_mm"),
                "depth": state.get("target_depth_mm"),
                "safety": is_safe
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("safety", run_safety_diagnostic)
_g.add_node("plan", compile_operation_plan)

_g.add_edge(START, "validate")
_g.add_edge("validate", "safety")
_g.add_edge("safety", "plan")
_g.add_edge("plan", END)

graph = _g.compile()
