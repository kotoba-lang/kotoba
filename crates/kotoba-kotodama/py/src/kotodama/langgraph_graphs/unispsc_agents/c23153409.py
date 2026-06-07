# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153409 — Welding (segment 23).

Bespoke graph logic for welding operations, covering setup, execution, and inspection.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153409"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153409"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    metal_type: str
    weld_method: str
    safety_check_passed: bool
    joint_integrity_score: float


def setup_welding_station(state: State) -> dict[str, Any]:
    """Initializes the welding parameters and performs a safety protocol check."""
    inp = state.get("input") or {}
    metal = inp.get("metal_type", "carbon_steel")
    method = inp.get("weld_method", "MIG")
    # Simulate a safety check based on presence of required PPE in input
    ppe_verified = inp.get("ppe_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:setup_welding_station"],
        "metal_type": metal,
        "weld_method": method,
        "safety_check_passed": ppe_verified,
    }


def perform_welding_operation(state: State) -> dict[str, Any]:
    """Simulates the physical welding process if safety checks are met."""
    if not state.get("safety_check_passed"):
        return {
            "log": [f"{UNISPSC_CODE}:perform_welding_operation:skipped_safety_fail"],
            "joint_integrity_score": 0.0,
        }

    method = state.get("weld_method")
    # TIG yields higher precision in this simulation
    integrity = 0.98 if method == "TIG" else 0.85

    return {
        "log": [f"{UNISPSC_CODE}:perform_welding_operation:success"],
        "joint_integrity_score": integrity,
    }


def finalize_inspection(state: State) -> dict[str, Any]:
    """Conducts a final quality check and prepares the output manifest."""
    score = state.get("joint_integrity_score", 0.0)
    passed = score > 0.8

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inspection"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "quality_pass": passed,
            "integrity_score": score,
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("setup", setup_welding_station)
_g.add_node("weld", perform_welding_operation)
_g.add_node("inspect", finalize_inspection)

_g.add_edge(START, "setup")
_g.add_edge("setup", "weld")
_g.add_edge("weld", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
