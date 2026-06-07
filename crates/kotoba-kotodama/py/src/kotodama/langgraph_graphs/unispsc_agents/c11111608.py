# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11111608 — Carbon Fiber.

Bespoke graph logic for Carbon Fiber material specification and grade evaluation.
This agent validates mechanical properties (tensile strength, modulus) and
categorizes the fiber by filament count and application grade.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11111608"
UNISPSC_TITLE = "Carbon Fiber"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11111608"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Carbon Fiber
    tensile_strength_mpa: float
    tensile_modulus_gpa: float
    filament_count_k: int
    is_aerospace_grade: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Extracts and validates raw material specifications from input."""
    inp = state.get("input") or {}
    strength = float(inp.get("tensile_strength", 0.0))
    modulus = float(inp.get("modulus", 0.0))
    count = int(inp.get("k_count", 12))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "tensile_strength_mpa": strength,
        "tensile_modulus_gpa": modulus,
        "filament_count_k": count,
    }


def evaluate_material_grade(state: State) -> dict[str, Any]:
    """Determines the grade based on tensile strength and modulus benchmarks."""
    strength = state.get("tensile_strength_mpa", 0.0)
    # Typically > 4500 MPa is high strength / aerospace grade
    is_aerospace = strength > 4500.0

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_material_grade"],
        "is_aerospace_grade": is_aerospace,
    }


def finalize_carbon_record(state: State) -> dict[str, Any]:
    """Compiles the final material certificate and validation status."""
    is_aero = state.get("is_aerospace_grade", False)
    strength = state.get("tensile_strength_mpa", 0.0)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "did": UNISPSC_DID,
        "metrics": {
            "strength": strength,
            "modulus": state.get("tensile_modulus_gpa", 0.0),
            "tow_size": f"{state.get('filament_count_k', 0)}k"
        },
        "grade": "Aerospace" if is_aero else "Industrial/Commercial",
        "certified": strength > 0,
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_carbon_record"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specifications)
_g.add_node("evaluate", evaluate_material_grade)
_g.add_node("finalize", finalize_carbon_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
