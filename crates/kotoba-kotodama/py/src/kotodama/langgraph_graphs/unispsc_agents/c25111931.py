# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111931 — Platform.
Bespoke logic for vehicle and structural platform specification and validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111931"
UNISPSC_TITLE = "Platform"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111931"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for "Platform"
    platform_type: str
    load_capacity_kg: float
    safety_margin: float
    material_compatibility: bool
    is_certified: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Analyzes input for platform requirements and identifies the platform type."""
    inp = state.get("input") or {}
    p_type = inp.get("type", "generic_industrial")
    capacity = float(inp.get("capacity", 1000.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "platform_type": p_type,
        "load_capacity_kg": capacity,
        "is_certified": False
    }


def analyze_structural_integrity(state: State) -> dict[str, Any]:
    """Calculates safety margins based on the load capacity and material types."""
    capacity = state.get("load_capacity_kg", 0.0)
    # Heuristic calculation for safety margin and material compatibility
    margin = 1.5 if capacity < 5000 else 2.2
    compatible = True if state.get("platform_type") != "volatile_environment" else False

    return {
        "log": [f"{UNISPSC_CODE}:analyze_structural_integrity"],
        "safety_margin": margin,
        "material_compatibility": compatible
    }


def certify_platform(state: State) -> dict[str, Any]:
    """Finalizes the platform configuration and issues a simulated certification."""
    margin = state.get("safety_margin", 0.0)
    compatible = state.get("material_compatibility", False)
    certified = margin >= 1.2 and compatible

    return {
        "log": [f"{UNISPSC_CODE}:certify_platform"],
        "is_certified": certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "platform_type": state.get("platform_type"),
            "certified": certified,
            "metrics": {
                "margin": margin,
                "load": state.get("load_capacity_kg")
            },
            "did": UNISPSC_DID,
            "status": "APPROVED" if certified else "REJECTED"
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("analyze", analyze_structural_integrity)
_g.add_node("certify", certify_platform)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
