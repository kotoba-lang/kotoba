# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111803 — Belt.
Bespoke logic for power transmission belt specification and lifecycle estimation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111803"
UNISPSC_TITLE = "Belt"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for "Belt" domain
    tension_spec_newtons: float
    material_grade: str
    safety_factor: float
    estimated_service_life_hours: int


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the belt dimensions and load requirements."""
    inp = state.get("input") or {}
    load = float(inp.get("load_kg", 0.0))
    width = float(inp.get("width_mm", 0.0))

    # Logic to determine material grade based on width/load
    grade = "Standard-Duty"
    if load > 500 or width > 100:
        grade = "Industrial-HD"

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "material_grade": grade,
        "tension_spec_newtons": round(load * 9.81 * 1.25, 2),
    }


def analyze_durability(state: State) -> dict[str, Any]:
    """Calculates expected service life based on grade and tension."""
    grade = state.get("material_grade", "Standard-Duty")
    tension = state.get("tension_spec_newtons", 0.0)

    base_hours = 12000 if grade == "Industrial-HD" else 3000
    # Higher tension relative to standard load reduces life
    stress_factor = 1.0 + (tension / 5000)
    life = int(base_hours / stress_factor)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_durability"],
        "safety_factor": 2.8 if grade == "Industrial-HD" else 1.6,
        "estimated_service_life_hours": life,
    }


def finalize_asset_data(state: State) -> dict[str, Any]:
    """Prepares the final result including metadata and calculated metrics."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "grade": state.get("material_grade"),
                "operating_tension_n": state.get("tension_spec_newtons"),
                "safety_margin": state.get("safety_factor"),
                "expected_life_hrs": state.get("estimated_service_life_hours"),
            },
            "status": "certified",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("analyze", analyze_durability)
_g.add_node("finalize", finalize_asset_data)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
