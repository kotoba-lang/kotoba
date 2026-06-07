# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121429 — Robot Reducer.

This bespoke agent implements a configuration and performance validation pipeline
for robotic speed reducers, ensuring mechanical specifications align with
robotic arm performance requirements.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121429"
UNISPSC_TITLE = "Robot Reducer"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121429"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Robot Reducer
    reduction_ratio: float
    rated_torque_nm: float
    max_backlash_arcmin: float
    precision_class: str
    thermal_rating_w: float


def analyze_specifications(state: State) -> dict[str, Any]:
    """Validates incoming mechanical requirements for the robot reducer."""
    inp = state.get("input") or {}
    ratio = float(inp.get("target_ratio", 50.0))
    backlash = float(inp.get("max_backlash", 1.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications"],
        "reduction_ratio": ratio,
        "max_backlash_arcmin": backlash,
        "precision_class": "high" if backlash < 3.0 else "standard",
    }


def calculate_performance(state: State) -> dict[str, Any]:
    """Computes output performance metrics based on ratio and efficiency."""
    ratio = state.get("reduction_ratio", 1.0)

    # Model high-precision planetary or harmonic drive characteristics
    efficiency = 0.92 if ratio > 80 else 0.96
    base_torque = 50.0  # Nm

    return {
        "log": [f"{UNISPSC_CODE}:calculate_performance"],
        "rated_torque_nm": base_torque * ratio * efficiency,
        "thermal_rating_w": 250.0 * (1.0 - efficiency),
    }


def finalize_actor_response(state: State) -> dict[str, Any]:
    """Prepares the final result payload for the Robot Reducer agent."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_actor_response"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "performance": {
                "ratio": state.get("reduction_ratio"),
                "torque_nm": round(state.get("rated_torque_nm", 0.0), 2),
                "precision": state.get("precision_class"),
                "thermal_load_w": round(state.get("thermal_rating_w", 0.0), 2),
            },
            "status": "configured",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_specifications)
_g.add_node("calculate", calculate_performance)
_g.add_node("finalize", finalize_actor_response)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
