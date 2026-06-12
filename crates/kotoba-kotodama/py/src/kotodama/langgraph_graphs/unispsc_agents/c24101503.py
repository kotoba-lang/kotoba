# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101503 — Dolly Spec.

This agent handles the technical specification and safety validation for
industrial dollies (UNISPSC 24101503) within the Material Handling segment.
It validates load requirements, selects appropriate wheel configurations,
and ensures compliance with material handling safety standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101503"
UNISPSC_TITLE = "Dolly Spec"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101503"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Dolly Spec
    load_capacity_kg: float
    wheel_type: str  # e.g., "pneumatic", "solid_rubber", "polyurethane"
    frame_material: str  # e.g., "aluminum", "steel", "polypropylene"
    safety_inspection_passed: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Initial validation of the dolly requirements and load capacity."""
    inp = state.get("input") or {}
    capacity = float(inp.get("required_capacity", 500.0))

    # Simple validation logic
    is_valid = 0 < capacity <= 5000  # Max 5 tons for this spec agent

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "load_capacity_kg": capacity,
        "safety_inspection_passed": is_valid
    }


def configure_engineering(state: State) -> dict[str, Any]:
    """Selects materials and components based on the validated load capacity."""
    capacity = state.get("load_capacity_kg", 0.0)

    if capacity > 1000:
        frame = "reinforced_steel"
        wheels = "heavy_duty_polyurethane"
    elif capacity > 250:
        frame = "aluminum_alloy"
        wheels = "solid_rubber"
    else:
        frame = "impact_resistant_polymer"
        wheels = "standard_nylon"

    return {
        "log": [f"{UNISPSC_CODE}:configure_engineering"],
        "frame_material": frame,
        "wheel_type": wheels
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final Dolly Spec document and certification result."""
    passed = state.get("safety_inspection_passed", False)
    capacity = state.get("load_capacity_kg")
    frame = state.get("frame_material")
    wheels = state.get("wheel_type")

    result_data = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "did": UNISPSC_DID,
        "spec_verified": passed,
        "details": {
            "capacity_rating": f"{capacity}kg",
            "frame": frame,
            "wheel_assembly": wheels,
            "compliance_standard": "ANSI/ITSDF B56.11.4"
        }
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": result_data
    }


# Graph Construction
_g = StateGraph(State)

_g.add_node("validate", validate_requirements)
_g.add_node("configure", configure_engineering)
_g.add_node("certify", finalize_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "configure")
_g.add_edge("configure", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
