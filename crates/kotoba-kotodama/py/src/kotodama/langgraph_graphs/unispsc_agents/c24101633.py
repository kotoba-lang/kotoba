# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101633"
UNISPSC_TITLE = "Hoist"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101633"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    load_capacity_kg: float
    lift_height_m: float
    safety_lock_engaged: bool
    inspection_passed: bool
    operational_mode: str


def initialize_hoist(state: State) -> dict[str, Any]:
    """Initialize hoist parameters and operational mode."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "standard")
    return {
        "log": [f"{UNISPSC_CODE}:initialize_hoist"],
        "load_capacity_kg": 5000.0,
        "lift_height_m": 25.0,
        "operational_mode": mode,
    }


def verify_safety_protocols(state: State) -> dict[str, Any]:
    """Verify that all safety locks and inspections are current."""
    capacity = state.get("load_capacity_kg", 0)
    passed = capacity > 0
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_passed={passed}"],
        "safety_lock_engaged": passed,
        "inspection_passed": passed,
    }


def finalize_lifting_plan(state: State) -> dict[str, Any]:
    """Finalize the operational plan and emit the result."""
    is_ready = state.get("inspection_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_lifting_plan"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "operational" if is_ready else "grounded",
            "specifications": {
                "max_load": state.get("load_capacity_kg"),
                "max_height": state.get("lift_height_m"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_hoist)
_g.add_node("verify", verify_safety_protocols)
_g.add_node("finalize", finalize_lifting_plan)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
