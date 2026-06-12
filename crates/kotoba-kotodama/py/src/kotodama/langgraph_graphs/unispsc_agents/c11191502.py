# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11191502 — Corn or maize (segment 11).

Bespoke graph for grain inspection and grading of corn/maize consignments.
This agent validates moisture content, assesses grain quality, and
assigns a standard grade for agricultural commerce.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11191502"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11191502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    moisture_percent: float
    bushel_weight: float
    grade_level: str
    is_non_gmo: bool


def inspect_grain(state: State) -> dict[str, Any]:
    """Inspects the grain for moisture content and physical weight."""
    inp = state.get("input") or {}
    moisture = float(inp.get("moisture", 14.0))
    weight = float(inp.get("weight", 56.0))
    non_gmo = bool(inp.get("non_gmo", False))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_grain"],
        "moisture_percent": moisture,
        "bushel_weight": weight,
        "is_non_gmo": non_gmo,
    }


def classify_quality(state: State) -> dict[str, Any]:
    """Determines the commercial grade based on moisture and weight."""
    moisture = state.get("moisture_percent", 0.0)
    weight = state.get("bushel_weight", 0.0)

    # Simplified USDA grading logic
    if moisture <= 14.0 and weight >= 56.0:
        grade = "US_NO_1"
    elif moisture <= 15.5 and weight >= 54.0:
        grade = "US_NO_2"
    else:
        grade = "SAMPLE_GRADE"

    return {
        "log": [f"{UNISPSC_CODE}:classify_quality(grade={grade})"],
        "grade_level": grade,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final actor response with certification details."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "quality": {
                "grade": state.get("grade_level"),
                "moisture": state.get("moisture_percent"),
                "non_gmo": state.get("is_non_gmo"),
            },
            "ok": state.get("grade_level") != "SAMPLE_GRADE",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_grain)
_g.add_node("classify", classify_quality)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "classify")
_g.add_edge("classify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
