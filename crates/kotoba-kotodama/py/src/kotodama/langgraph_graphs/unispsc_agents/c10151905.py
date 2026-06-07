# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151905 — Fresh Produce (segment 10).

Bespoke graph logic for handling fresh produce inspection, grading, and
logistics readiness. This agent evaluates ripeness indices, temperature
controls, and quality standards for fresh agricultural outputs.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151905"
UNISPSC_TITLE = "Fresh Produce"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151905"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    temperature_c: float
    ripeness_index: float
    quality_grade: str
    is_organic: bool
    shelf_life_prediction: int


def quality_inspection(state: State) -> dict[str, Any]:
    """Inspects the fresh produce for temperature and ripeness parameters."""
    inp = state.get("input") or {}
    # Default to safe refrigerated transport temperature if not provided
    temp = float(inp.get("temperature", 4.0))
    # Ripeness index 0.0 (unripe) to 1.0 (overripe)
    ripeness = float(inp.get("ripeness", 0.5))
    organic = bool(inp.get("organic", False))

    return {
        "log": [f"{UNISPSC_CODE}:quality_inspection"],
        "temperature_c": temp,
        "ripeness_index": ripeness,
        "is_organic": organic,
    }


def grade_assessment(state: State) -> dict[str, Any]:
    """Assigns a quality grade based on physical and environmental metrics."""
    temp = state.get("temperature_c", 0.0)
    ripeness = state.get("ripeness_index", 0.0)

    # Grading logic: Premium requires tight temperature and mid-range ripeness
    if 1.0 <= temp <= 6.0 and 0.4 <= ripeness <= 0.7:
        grade = "Grade-A-Premium"
        shelf_life = 14
    elif 0.0 <= temp <= 10.0:
        grade = "Grade-B-Standard"
        shelf_life = 7
    else:
        grade = "Grade-C-Discount"
        shelf_life = 3

    return {
        "log": [f"{UNISPSC_CODE}:grade_assessment"],
        "quality_grade": grade,
        "shelf_life_prediction": shelf_life,
    }


def emit_manifest(state: State) -> dict[str, Any]:
    """Finalizes the inspection manifest and results."""
    grade = state.get("quality_grade", "Unclassified")
    shelf_life = state.get("shelf_life_prediction", 0)
    is_organic = state.get("is_organic", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "grade": grade,
            "organic": is_organic,
            "shelf_life_days": shelf_life,
            "verified": grade != "Grade-C-Discount",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("quality_inspection", quality_inspection)
_g.add_node("grade_assessment", grade_assessment)
_g.add_node("emit_manifest", emit_manifest)

_g.add_edge(START, "quality_inspection")
_g.add_edge("quality_inspection", "grade_assessment")
_g.add_edge("grade_assessment", "emit_manifest")
_g.add_edge("emit_manifest", END)

graph = _g.compile()
