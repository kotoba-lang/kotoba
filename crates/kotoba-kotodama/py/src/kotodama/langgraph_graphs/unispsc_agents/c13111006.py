# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111006 — Anthracite (segment 13).

Bespoke graph for anthracite coal processing and quality verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111006"
UNISPSC_TITLE = "Anthracite"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111006"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    carbon_percentage: float
    ash_percentage: float
    sulfur_percentage: float
    quality_grade: str


def analyze_composition(state: State) -> dict[str, Any]:
    """Extracts mineral composition from the input batch data."""
    inp = state.get("input") or {}
    # Simulate extraction of data from input with defaults for anthracite
    carbon = float(inp.get("carbon", 86.5))
    ash = float(inp.get("ash", 4.2))
    sulfur = float(inp.get("sulfur", 0.55))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "carbon_percentage": carbon,
        "ash_percentage": ash,
        "sulfur_percentage": sulfur,
    }


def determine_grade(state: State) -> dict[str, Any]:
    """Calculates the quality grade based on carbon and ash content."""
    carbon = state.get("carbon_percentage", 0.0)
    ash = state.get("ash_percentage", 100.0)

    if carbon > 92.0 and ash < 4.0:
        grade = "Ultra-High Grade"
    elif carbon > 86.0 and ash < 10.0:
        grade = "High Grade"
    else:
        grade = "Standard Grade"

    return {
        "log": [f"{UNISPSC_CODE}:determine_grade:{grade}"],
        "quality_grade": grade,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Produces the final certification result for the anthracite batch."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "composition": {
                "carbon": state.get("carbon_percentage"),
                "ash": state.get("ash_percentage"),
                "sulfur": state.get("sulfur_percentage"),
            },
            "grade": state.get("quality_grade"),
            "certified": True,
            "status": "ready_for_dispatch",
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_composition", analyze_composition)
_g.add_node("determine_grade", determine_grade)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "analyze_composition")
_g.add_edge("analyze_composition", "determine_grade")
_g.add_edge("determine_grade", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
