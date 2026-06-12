# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Bespoke LangGraph agent for UNISPSC 25174601 (Seat Cover).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174601"
UNISPSC_TITLE = "Seat Cover"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Seat Cover
    material_type: str
    fit_specification: str
    airbag_compatible: bool
    quality_grade: str


def validate_requirements(state: State) -> dict[str, Any]:
    """Analyzes input for material and compatibility requirements."""
    inp = state.get("input") or {}
    material = inp.get("material", "polyester")
    fit = inp.get("fit", "universal")
    airbag = inp.get("airbag_safe", True)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "material_type": material,
        "fit_specification": fit,
        "airbag_compatible": airbag,
    }


def grade_selection(state: State) -> dict[str, Any]:
    """Assigns a quality grade based on material and fit."""
    material = state.get("material_type", "polyester")
    fit = state.get("fit_specification", "universal")

    if material == "leather" and fit == "custom":
        grade = "premium"
    elif material == "neoprene":
        grade = "sport"
    else:
        grade = "standard"

    return {
        "log": [f"{UNISPSC_CODE}:grade_selection"],
        "quality_grade": grade,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Compiles the final seat cover specification and result."""
    grade = state.get("quality_grade")
    airbag = state.get("airbag_compatible")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "material": state.get("material_type"),
                "fit": state.get("fit_specification"),
                "grade": grade,
                "safety_certified": airbag,
            },
            "status": "ready_for_production",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_requirements", validate_requirements)
_g.add_node("grade_selection", grade_selection)
_g.add_node("finalize_specification", finalize_specification)

_g.add_edge(START, "validate_requirements")
_g.add_edge("validate_requirements", "grade_selection")
_g.add_edge("grade_selection", "finalize_specification")
_g.add_edge("finalize_specification", END)

graph = _g.compile()
