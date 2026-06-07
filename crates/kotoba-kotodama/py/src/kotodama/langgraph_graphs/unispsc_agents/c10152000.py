# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10152000 — Grain (segment 10).

This bespoke implementation handles quality inspection and grading for various
types of grain, ensuring they meet standards for moisture, protein, and
foreign material content before certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10152000"
UNISPSC_TITLE = "Grain"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10152000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    moisture_content: float
    protein_level: float
    foreign_material_pct: float
    assigned_grade: str


def inspect_quality(state: State) -> dict[str, Any]:
    """Inspects the physical properties of the grain batch."""
    inp = state.get("input") or {}
    moisture = float(inp.get("moisture", 12.0))
    protein = float(inp.get("protein", 11.5))
    foreign = float(inp.get("foreign_matter", 0.5))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_quality (moisture={moisture}%, protein={protein}%)"],
        "moisture_content": moisture,
        "protein_level": protein,
        "foreign_material_pct": foreign,
    }


def grade_grain(state: State) -> dict[str, Any]:
    """Determines the commercial grade based on inspected metrics."""
    moisture = state.get("moisture_content", 0.0)
    protein = state.get("protein_level", 0.0)
    foreign = state.get("foreign_material_pct", 1.0)

    # Simple logic for grain grading
    if moisture > 14.5:
        grade = "High Moisture / Feed Only"
    elif protein > 13.0 and foreign < 0.2:
        grade = "Premium Milling"
    elif protein > 11.0 and foreign < 0.5:
        grade = "Standard Milling"
    else:
        grade = "General Utility"

    return {
        "log": [f"{UNISPSC_CODE}:grade_grain (assigned={grade})"],
        "assigned_grade": grade,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Finalizes the processing and prepares the result certificate."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "quality_metrics": {
                "moisture": state.get("moisture_content"),
                "protein": state.get("protein_level"),
                "foreign_material": state.get("foreign_material_pct"),
            },
            "grade": state.get("assigned_grade"),
            "status": "Certified",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_quality", inspect_quality)
_g.add_node("grade_grain", grade_grain)
_g.add_node("certify_batch", certify_batch)

_g.add_edge(START, "inspect_quality")
_g.add_edge("inspect_quality", "grade_grain")
_g.add_edge("grade_grain", "certify_batch")
_g.add_edge("certify_batch", END)

graph = _g.compile()
