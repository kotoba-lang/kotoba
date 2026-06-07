# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111005 — Crude Oil.

This agent handles the analysis and grading of crude oil batches based on
chemical properties like API gravity and sulfur content to determine market
classification (e.g., Light Sweet, Heavy Sour).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111005"
UNISPSC_TITLE = "Crude Oil"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111005"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Crude Oil
    api_gravity: float
    sulfur_percent: float
    crude_grade: str
    origin_well_id: str
    is_compliant: bool


def inspect_properties(state: State) -> dict[str, Any]:
    """Extracts chemical properties and origin data from input."""
    inp = state.get("input") or {}
    api = float(inp.get("api_gravity", 0.0))
    sulfur = float(inp.get("sulfur_percent", 0.0))
    well_id = str(inp.get("well_id", "unknown"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_properties"],
        "api_gravity": api,
        "sulfur_percent": sulfur,
        "origin_well_id": well_id,
        "is_compliant": api > 0,
    }


def grade_batch(state: State) -> dict[str, Any]:
    """Determines the market grade based on API gravity and sulfur content."""
    api = state.get("api_gravity", 0.0)
    sulfur = state.get("sulfur_percent", 0.0)

    # Simplified grading logic
    # Light: API > 31.1, Medium: 22.3 < API < 31.1, Heavy: API < 22.3
    # Sweet: Sulfur < 0.5%, Sour: Sulfur > 0.5%
    weight = "Light" if api > 31.1 else "Medium" if api > 22.3 else "Heavy"
    sweetness = "Sweet" if sulfur < 0.5 else "Sour"
    grade = f"{weight} {sweetness}"

    return {
        "log": [f"{UNISPSC_CODE}:grade_batch"],
        "crude_grade": grade,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final certificate of analysis and transaction record."""
    grade = state.get("crude_grade", "Unclassified")
    well_id = state.get("origin_well_id", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "manifest": {
                "grade": grade,
                "origin": well_id,
                "api_gravity": state.get("api_gravity"),
                "sulfur_content": f"{state.get('sulfur_percent')}%",
            },
            "status": "certified" if state.get("is_compliant") else "flagged",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_properties)
_g.add_node("grade", grade_batch)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "grade")
_g.add_edge("grade", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
