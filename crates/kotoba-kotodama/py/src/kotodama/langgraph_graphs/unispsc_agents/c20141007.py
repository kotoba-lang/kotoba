# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141007 — Bearing (segment 20).

Bespoke logic for mechanical bearing specification validation and
performance parameter assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141007"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141007"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Bearing specifications
    bore_diameter_mm: float
    load_capacity_kn: float
    lubrication_type: str
    is_valid_spec: bool


def validate_dimensions(state: State) -> dict[str, Any]:
    """Validates core bearing dimensions from the input payload."""
    inp = state.get("input") or {}
    bore = float(inp.get("bore", 0.0))
    load = float(inp.get("load", 0.0))

    # Simple validation rule: bore and load must be positive
    valid = bore > 0 and load > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_dimensions"],
        "bore_diameter_mm": bore,
        "load_capacity_kn": load,
        "is_valid_spec": valid,
    }


def determine_lubrication(state: State) -> dict[str, Any]:
    """Selects appropriate lubrication based on the load capacity."""
    load = state.get("load_capacity_kn", 0.0)

    # Heavy-duty bearings (>100kN) require high-viscosity synthetic grease
    if load > 100.0:
        lube = "synthetic_grease"
    elif load > 20.0:
        lube = "standard_lithium"
    else:
        lube = "light_oil"

    return {
        "log": [f"{UNISPSC_CODE}:determine_lubrication"],
        "lubrication_type": lube,
    }


def finalize_bearing_data(state: State) -> dict[str, Any]:
    """Consolidates valid data into the final result dictionary."""
    valid = state.get("is_valid_spec", False)
    bore = state.get("bore_diameter_mm", 0.0)
    lube = state.get("lubrication_type", "none")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_bearing_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "valid": valid,
            "specs": {
                "bore_diameter": f"{bore}mm",
                "lubricant": lube,
            },
            "did": UNISPSC_DID,
            "ok": valid,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_dimensions", validate_dimensions)
_g.add_node("determine_lubrication", determine_lubrication)
_g.add_node("finalize_bearing_data", finalize_bearing_data)

_g.add_edge(START, "validate_dimensions")
_g.add_edge("validate_dimensions", "determine_lubrication")
_g.add_edge("determine_lubrication", "finalize_bearing_data")
_g.add_edge("finalize_bearing_data", END)

graph = _g.compile()
