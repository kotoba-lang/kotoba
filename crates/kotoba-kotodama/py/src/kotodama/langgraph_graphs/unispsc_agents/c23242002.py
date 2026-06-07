# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242002 — Broaching (segment 23).
Bespoke logic for precision metal removal using toothed broaching tools.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242002"
UNISPSC_TITLE = "Broaching"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Broaching
    workpiece_material: str
    broach_geometry: str
    target_tolerance: float
    calculated_stroke_speed: float
    coolant_type: str


def analyze_geometry(state: State) -> dict[str, Any]:
    """Determine the type of broaching operation required (internal vs external)."""
    inp = state.get("input") or {}
    material = inp.get("material", "mild_steel")
    geometry = inp.get("geometry", "internal_spline")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_geometry -> {geometry}"],
        "workpiece_material": material,
        "broach_geometry": geometry,
    }


def configure_machining_params(state: State) -> dict[str, Any]:
    """Calculate feed rates and stroke speeds based on material properties."""
    material = state.get("workpiece_material", "mild_steel")

    # Mock parameter selection for broaching operations
    if material == "stainless_steel":
        speed = 12.0
        coolant = "sulfurized_oil"
    elif material == "brass":
        speed = 35.0
        coolant = "synthetic_emulsion"
    else:
        speed = 22.0
        coolant = "soluble_oil"

    return {
        "log": [f"{UNISPSC_CODE}:configure_machining_params -> {speed} fpm"],
        "calculated_stroke_speed": speed,
        "coolant_type": coolant,
        "target_tolerance": 0.0005,
    }


def finalize_operational_spec(state: State) -> dict[str, Any]:
    """Compile the final machining specification for the broaching unit."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_operational_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "operation": state.get("broach_geometry"),
            "settings": {
                "speed_fpm": state.get("calculated_stroke_speed"),
                "coolant": state.get("coolant_type"),
                "tolerance_inch": state.get("target_tolerance"),
            },
            "did": UNISPSC_DID,
            "status": "ready",
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_geometry", analyze_geometry)
_g.add_node("configure_machining_params", configure_machining_params)
_g.add_node("finalize_operational_spec", finalize_operational_spec)

_g.add_edge(START, "analyze_geometry")
_g.add_edge("analyze_geometry", "configure_machining_params")
_g.add_edge("configure_machining_params", "finalize_operational_spec")
_g.add_edge("finalize_operational_spec", END)

graph = _g.compile()
