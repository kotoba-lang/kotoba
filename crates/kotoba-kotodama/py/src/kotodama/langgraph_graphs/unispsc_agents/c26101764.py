# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101764 — Liner (segment 26).

This agent manages the lifecycle and specification validation for industrial liners
used in power generation machinery, focusing on bore integrity and material thermal
resistance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101764"
UNISPSC_TITLE = "Liner"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101764"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Liner
    bore_diameter_mm: float
    material_hardness_hrc: int
    thermal_stress_rating: str
    geometry_valid: bool


def verify_geometry(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and bore specifications of the liner."""
    inp = state.get("input") or {}
    bore = float(inp.get("bore_diameter", 0.0))
    is_valid = 50.0 <= bore <= 1000.0  # Typical range for power gen liners

    return {
        "log": [f"{UNISPSC_CODE}:verify_geometry"],
        "bore_diameter_mm": bore,
        "geometry_valid": is_valid,
    }


def analyze_thermal_load(state: State) -> dict[str, Any]:
    """Determines the thermal stress rating based on the intended power output."""
    inp = state.get("input") or {}
    power_kw = inp.get("target_power_kw", 0)

    if power_kw > 5000:
        rating = "CRITICAL"
    elif power_kw > 1000:
        rating = "HIGH"
    else:
        rating = "STANDARD"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_thermal_load"],
        "thermal_stress_rating": rating,
        "material_hardness_hrc": 52 if rating == "CRITICAL" else 45,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Compiles the final liner data sheet and verification status."""
    is_ok = state.get("geometry_valid", False)
    rating = state.get("thermal_stress_rating", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "bore_mm": state.get("bore_diameter_mm"),
                "hardness_hrc": state.get("material_hardness_hrc"),
                "thermal_rating": rating,
            },
            "status": "APPROVED" if is_ok else "REJECTED",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_geometry", verify_geometry)
_g.add_node("analyze_thermal_load", analyze_thermal_load)
_g.add_node("finalize_specification", finalize_specification)

_g.add_edge(START, "verify_geometry")
_g.add_edge("verify_geometry", "analyze_thermal_load")
_g.add_edge("analyze_thermal_load", "finalize_specification")
_g.add_edge("finalize_specification", END)

graph = _g.compile()
