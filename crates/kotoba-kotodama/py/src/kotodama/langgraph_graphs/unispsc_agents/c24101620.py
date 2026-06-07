# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101620 — Crane (segment 24).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101620"
UNISPSC_TITLE = "Crane"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101620"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    lift_weight_tons: float
    boom_extension_meters: float
    safety_check_ok: bool
    wind_speed_kmh: float


def initialize_lift(state: State) -> dict[str, Any]:
    """Initialize crane state from input parameters."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:initialize_lift"],
        "lift_weight_tons": float(inp.get("weight", 0.0)),
        "boom_extension_meters": float(inp.get("extension", 10.0)),
        "wind_speed_kmh": float(inp.get("wind", 0.0)),
        "safety_check_ok": False,
    }


def verify_stability(state: State) -> dict[str, Any]:
    """Check if the lift is within safe operating parameters."""
    weight = state.get("lift_weight_tons", 0.0)
    extension = state.get("boom_extension_meters", 10.0)
    wind = state.get("wind_speed_kmh", 0.0)

    # Simplified safety logic for heavy lifting equipment:
    # Max safe capacity decreases as the boom extends further.
    capacity_rating = 500.0 / (extension + 1.0)
    wind_threshold = 45.0

    is_safe = (weight <= capacity_rating) and (wind < wind_threshold)

    return {
        "log": [f"{UNISPSC_CODE}:verify_stability - status: {'safe' if is_safe else 'unsafe'}"],
        "safety_check_ok": is_safe,
    }


def finalize_operation(state: State) -> dict[str, Any]:
    """Produce the final results and completion log."""
    safe = state.get("safety_check_ok", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_operation"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "authorized": safe,
            "action": "PROCEED" if safe else "HALT",
            "reason": "Stability check passed" if safe else "Load capacity exceeded or high wind",
        },
    }


_g = StateGraph(State)

_g.add_node("initialize_lift", initialize_lift)
_g.add_node("verify_stability", verify_stability)
_g.add_node("finalize_operation", finalize_operation)

_g.add_edge(START, "initialize_lift")
_g.add_edge("initialize_lift", "verify_stability")
_g.add_edge("verify_stability", "finalize_operation")
_g.add_edge("finalize_operation", END)

graph = _g.compile()
