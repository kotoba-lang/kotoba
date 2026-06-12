# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101615 — Ramp (segment 24).
Bespoke implementation for material handling ramp specifications and safety.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101615"
UNISPSC_TITLE = "Ramp"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101615"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Ramp
    load_capacity_kg: float
    incline_angle_degrees: float
    surface_texture: str
    safety_compliant: bool


def inspect_requirements(state: State) -> dict[str, Any]:
    """Analyzes the input requirements for the ramp specification."""
    inp = state.get("input") or {}
    load = float(inp.get("target_load", 1000.0))
    angle = float(inp.get("max_angle", 12.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_requirements"],
        "load_capacity_kg": load,
        "incline_angle_degrees": angle,
    }


def evaluate_safety_margins(state: State) -> dict[str, Any]:
    """Determines safety compliance based on incline and load."""
    load = state.get("load_capacity_kg", 0.0)
    angle = state.get("incline_angle_degrees", 0.0)

    # Safety logic for ramps
    is_safe = angle <= 15.0 and load <= 5000.0
    material = "diamond_plate_steel" if load > 2000.0 else "aluminum_grid"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_safety_margins -> safe={is_safe}"],
        "safety_compliant": is_safe,
        "surface_texture": material,
    }


def synthesize_deployment(state: State) -> dict[str, Any]:
    """Finalizes the ramp configuration and result payload."""
    is_safe = state.get("safety_compliant", False)

    final_result = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "status": "approved" if is_safe else "rejected",
        "configuration": {
            "load_limit": state.get("load_capacity_kg"),
            "angle": state.get("incline_angle_degrees"),
            "material": state.get("surface_texture"),
        }
    }

    return {
        "log": [f"{UNISPSC_CODE}:synthesize_deployment"],
        "result": final_result,
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_requirements)
_g.add_node("evaluate", evaluate_safety_margins)
_g.add_node("synthesize", synthesize_deployment)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "evaluate")
_g.add_edge("evaluate", "synthesize")
_g.add_edge("synthesize", END)

graph = _g.compile()
