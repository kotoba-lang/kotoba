# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26121521 — Bronze Wire (segment 26).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26121521"
UNISPSC_TITLE = "Bronze Wire"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26121521"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for Bronze Wire
    alloy_composition: str
    gauge_awg: int
    tensile_strength_mpa: float
    conductivity_rating: float
    quality_certification: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the input metallurgical specifications for the bronze wire."""
    inp = state.get("input") or {}
    alloy = str(inp.get("alloy", "Phosphor Bronze"))
    gauge = int(inp.get("gauge", 18))

    # Logic: ensure gauge is within standard production limits
    is_valid = 0 < gauge < 50

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "alloy_composition": alloy,
        "gauge_awg": gauge,
        "quality_certification": is_valid
    }


def compute_material_properties(state: State) -> dict[str, Any]:
    """Calculates physical properties based on alloy and wire gauge."""
    alloy = state.get("alloy_composition", "Phosphor Bronze")

    # Assign properties based on simulated alloy lookups
    if "Phosphor" in alloy:
        strength = 550.0
        conductivity = 15.0
    elif "Silicon" in alloy:
        strength = 620.0
        conductivity = 7.0
    else:
        strength = 450.0
        conductivity = 12.0

    return {
        "log": [f"{UNISPSC_CODE}:compute_material_properties"],
        "tensile_strength_mpa": strength,
        "conductivity_rating": conductivity
    }


def generate_technical_manifest(state: State) -> dict[str, Any]:
    """Compiles the final technical specification and metadata result."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_technical_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "alloy": state.get("alloy_composition"),
                "gauge": state.get("gauge_awg"),
                "tensile_strength_mpa": state.get("tensile_strength_mpa"),
                "iacs_conductivity": state.get("conductivity_rating")
            },
            "certified": state.get("quality_certification", False)
        }
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specification)
_g.add_node("compute", compute_material_properties)
_g.add_node("manifest", generate_technical_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "manifest")
_g.add_edge("manifest", END)

graph = _g.compile()
