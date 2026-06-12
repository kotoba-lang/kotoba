# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121416 — Linear Bearing (segment 20).

Bespoke graph logic for validating and certifying linear bearing specifications,
including shaft diameter, static load capacity, and precision classification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121416"
UNISPSC_TITLE = "Linear Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121416"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    shaft_diameter_mm: float
    static_load_kn: float
    precision_grade: str
    is_preloaded: bool
    material_hardness_hrc: int


def validate_specs(state: State) -> dict[str, Any]:
    """Extract and validate mechanical specifications from input."""
    inp = state.get("input") or {}
    diameter = float(inp.get("diameter", 12.0))
    load = float(inp.get("load", 1.5))
    hardness = int(inp.get("hardness", 58))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "shaft_diameter_mm": diameter,
        "static_load_kn": load,
        "material_hardness_hrc": hardness,
        "is_preloaded": inp.get("preloaded", False)
    }


def compute_precision(state: State) -> dict[str, Any]:
    """Determine precision grade based on diameter and preload requirements."""
    diam = state.get("shaft_diameter_mm", 0.0)
    preloaded = state.get("is_preloaded", False)

    # Logic: Highly preloaded small-diameter bearings are usually high precision
    if diam < 25 and preloaded:
        grade = "High (P5)"
    elif diam < 50:
        grade = "Standard (P0)"
    else:
        grade = "Heavy Duty (P0)"

    return {
        "log": [f"{UNISPSC_CODE}:compute_precision"],
        "precision_grade": grade
    }


def certify_bearing(state: State) -> dict[str, Any]:
    """Finalize the bearing certification result."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_bearing"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certification": {
                "nominal_diameter": f"{state.get('shaft_diameter_mm')}mm",
                "load_rating": f"{state.get('static_load_kn')}kN",
                "grade": state.get("precision_grade"),
                "hardness": f"{state.get('material_hardness_hrc')} HRC"
            },
            "compliant": state.get("material_hardness_hrc", 0) >= 50
        }
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("precision", compute_precision)
_g.add_node("certify", certify_bearing)

_g.add_edge(START, "validate")
_g.add_edge("validate", "precision")
_g.add_edge("precision", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
