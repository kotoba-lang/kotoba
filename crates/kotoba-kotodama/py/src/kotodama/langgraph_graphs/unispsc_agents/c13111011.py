# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111011 — Crude (segment 13).

Bespoke logic for handling crude raw material state, including quality
metrics like API gravity and sulfur content.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111011"
UNISPSC_TITLE = "Crude"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111011"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Crude
    api_gravity: float
    sulfur_content: float
    viscosity: float
    grade: str
    is_compliant: bool


def inspect_crude(state: State) -> dict[str, Any]:
    """Inspects raw input for crude oil characteristics."""
    inp = state.get("input") or {}
    api = float(inp.get("api_gravity", 30.0))
    sulfur = float(inp.get("sulfur_content", 0.5))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_crude"],
        "api_gravity": api,
        "sulfur_content": sulfur,
        "is_compliant": api > 10.0  # Basic check for liquid crude
    }


def grade_crude(state: State) -> dict[str, Any]:
    """Categorizes the crude based on API gravity and sulfur content."""
    api = state.get("api_gravity", 30.0)
    sulfur = state.get("sulfur_content", 0.5)

    # Simple grading logic
    if api > 31.1:
        base = "Light"
    elif api > 22.3:
        base = "Medium"
    else:
        base = "Heavy"

    sweetness = "Sweet" if sulfur < 0.5 else "Sour"
    grade = f"{base} {sweetness}"

    return {
        "log": [f"{UNISPSC_CODE}:grade_crude({grade})"],
        "grade": grade
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Emits the final certification for the crude batch."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "grade": state.get("grade"),
            "api_gravity": state.get("api_gravity"),
            "sulfur_content": state.get("sulfur_content"),
            "certified": state.get("is_compliant", False),
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_crude)
_g.add_node("grade", grade_crude)
_g.add_node("certify", certify_batch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "grade")
_g.add_edge("grade", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
