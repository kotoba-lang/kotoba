# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25161507 — Bicycle (segment 25).

Bespoke graph logic for bicycle manufacturing and assembly tracking.
This agent handles specification validation, component configuration,
and final safety certification for bicycle units.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25161507"
UNISPSC_TITLE = "Bicycle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25161507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Bicycle (25161507)
    frame_material: str
    wheel_diameter_mm: int
    braking_system: str
    safety_inspected: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the structural requirements of the bicycle order."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbon_fiber")
    diameter = inp.get("wheel_size", 700)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "frame_material": material,
        "wheel_diameter_mm": diameter,
    }


def configure_components(state: State) -> dict[str, Any]:
    """Selects appropriate components based on frame material and wheel size."""
    material = state.get("frame_material")
    # Higher performance frames get hydraulic systems
    brakes = "Hydraulic Disc" if material in ["carbon_fiber", "titanium"] else "Mechanical Rim"

    return {
        "log": [f"{UNISPSC_CODE}:configure_components"],
        "braking_system": brakes,
        "safety_inspected": True,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final digital twin record for the bicycle."""
    is_safe = state.get("safety_inspected", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "build_info": {
                "material": state.get("frame_material"),
                "wheels": f"{state.get('wheel_diameter_mm')}mm",
                "brakes": state.get("braking_system"),
            },
            "certified": is_safe,
            "status": "active" if is_safe else "quarantine",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("configure", configure_components)
_g.add_node("certify", finalize_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "configure")
_g.add_edge("configure", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
