# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101606 — Stacker (segment 24).
Bespoke logic for automated material handling and stacking operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101606"
UNISPSC_TITLE = "Stacker"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for material handling
    load_weight_kg: float
    max_capacity_kg: float
    stack_height_mm: int
    safety_clearance_verified: bool


def inspect_load(state: State) -> dict[str, Any]:
    """Inspects the physical properties of the load to be stacked."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))
    capacity = float(inp.get("rated_capacity", 2000.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_load"],
        "load_weight_kg": weight,
        "max_capacity_kg": capacity,
    }


def verify_stability(state: State) -> dict[str, Any]:
    """Calculates if the load is within safe stacking parameters."""
    weight = state.get("load_weight_kg", 0.0)
    capacity = state.get("max_capacity_kg", 2000.0)

    # Ensure weight does not exceed 95% of rated capacity for safety margin
    is_safe = weight <= (capacity * 0.95)
    target_height = 1200 if is_safe else 0

    return {
        "log": [f"{UNISPSC_CODE}:verify_stability"],
        "safety_clearance_verified": is_safe,
        "stack_height_mm": target_height,
    }


def finalize_stacking(state: State) -> dict[str, Any]:
    """Records the stacking result and emits operational telemetry."""
    success = state.get("safety_clearance_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_stacking"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "LOAD_PLACED" if success else "SAFETY_ABORT",
            "metrics": {
                "weight": state.get("load_weight_kg"),
                "height": state.get("stack_height_mm"),
            },
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_load", inspect_load)
_g.add_node("verify_stability", verify_stability)
_g.add_node("finalize_stacking", finalize_stacking)

_g.add_edge(START, "inspect_load")
_g.add_edge("inspect_load", "verify_stability")
_g.add_edge("verify_stability", "finalize_stacking")
_g.add_edge("finalize_stacking", END)

graph = _g.compile()
