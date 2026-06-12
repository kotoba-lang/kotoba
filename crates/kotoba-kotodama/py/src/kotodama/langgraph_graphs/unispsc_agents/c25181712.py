# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25181712 — Trailer (segment 25).

Bespoke graph logic for trailer registration and safety assessment.
This agent validates mechanical specifications and ensures compliance
with load-to-axle safety ratios before finalizing inventory status.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25181712"
UNISPSC_TITLE = "Trailer"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25181712"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Trailer
    trailer_type: str
    axle_count: int
    max_load_kg: float
    safety_inspection_passed: bool


def inspect_specs(state: State) -> dict[str, Any]:
    """Node: Inspect physical specifications of the trailer."""
    inp = state.get("input") or {}
    t_type = str(inp.get("type", "flatbed"))
    axles = int(inp.get("axles", 2))
    load = float(inp.get("max_load", 10000.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs -> type:{t_type}, axles:{axles}"],
        "trailer_type": t_type,
        "axle_count": axles,
        "max_load_kg": load,
    }


def assess_safety(state: State) -> dict[str, Any]:
    """Node: Assess structural safety based on load-to-axle ratios."""
    load = state.get("max_load_kg", 0.0)
    axles = state.get("axle_count", 1)

    # Requirement: Loads over 12,000kg require at least 3 axles for stability
    is_safe = True
    if load > 12000.0 and axles < 3:
        is_safe = False

    return {
        "log": [f"{UNISPSC_CODE}:assess_safety -> {'compliant' if is_safe else 'violation'}"],
        "safety_inspection_passed": is_safe,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Node: Register the trailer in the logistics inventory system."""
    passed = state.get("safety_inspection_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "certified" if passed else "quarantined",
            "specs": {
                "type": state.get("trailer_type"),
                "axle_count": state.get("axle_count"),
                "max_load_kg": state.get("max_load_kg"),
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specs", inspect_specs)
_g.add_node("assess_safety", assess_safety)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "assess_safety")
_g.add_edge("assess_safety", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
