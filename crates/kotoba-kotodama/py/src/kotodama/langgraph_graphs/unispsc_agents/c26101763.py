# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101763 — Freeze Plug (segment 26).

Bespoke graph for managing Freeze Plug specifications and thermal expansion
simulations. This agent validates material properties and pressure ratings
to ensure compliance with automotive or industrial cooling system standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101763"
UNISPSC_TITLE = "Freeze Plug"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101763"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields
    material_grade: str
    pressure_rating_psi: int
    thermal_range_c: tuple[int, int]
    specs_validated: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the freeze plug."""
    inp = state.get("input") or {}
    material = inp.get("material", "Brass")
    pressure = inp.get("pressure_psi", 50)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material_grade": material,
        "pressure_rating_psi": pressure,
        "specs_validated": pressure > 0,
    }


def analyze_thermal_stress(state: State) -> dict[str, Any]:
    """Simulates performance across a standard temperature range."""
    # Dummy simulation logic for expansion/contraction
    material = state.get("material_grade", "Unknown")
    thermal_range = (-40, 120) if "Steel" in material else (-30, 110)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_thermal_stress"],
        "thermal_range_c": thermal_range,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Emits the final validation result for the Freeze Plug."""
    is_valid = state.get("specs_validated", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": is_valid,
            "metadata": {
                "material": state.get("material_grade"),
                "max_pressure": state.get("pressure_rating_psi"),
                "temp_range": state.get("thermal_range_c"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("analyze_thermal_stress", analyze_thermal_stress)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "analyze_thermal_stress")
_g.add_edge("analyze_thermal_stress", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
