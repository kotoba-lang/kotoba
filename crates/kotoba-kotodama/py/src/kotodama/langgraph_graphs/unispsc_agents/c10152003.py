# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10152003 — Corn (segment 10).

Bespoke graph logic for corn quality assessment, grading, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10152003"
UNISPSC_TITLE = "Corn"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10152003"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Corn
    moisture_percentage: float
    corn_grade: str
    harvest_batch_id: str
    organic_certified: bool


def inspect_moisture(state: State) -> dict[str, Any]:
    """Inspects the moisture content of the corn batch."""
    inp = state.get("input") or {}
    moisture = float(inp.get("moisture", 15.5))
    batch_id = str(inp.get("batch_id", "BATCH-DEFAULT-CORN"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_moisture batch={batch_id} moisture={moisture}%"],
        "moisture_percentage": moisture,
        "harvest_batch_id": batch_id,
    }


def grade_batch(state: State) -> dict[str, Any]:
    """Determines the grade of the corn based on moisture and quality criteria."""
    moisture = state.get("moisture_percentage", 0.0)

    # Simplified USDA grading logic for yellow corn
    if moisture <= 14.0:
        grade = "No. 1 Yellow"
    elif moisture <= 15.5:
        grade = "No. 2 Yellow"
    else:
        grade = "Sample Grade (High Moisture)"

    return {
        "log": [f"{UNISPSC_CODE}:grade_batch assign_grade='{grade}'"],
        "corn_grade": grade,
        "organic_certified": bool(state.get("input", {}).get("organic", False))
    }


def certify_yield(state: State) -> dict[str, Any]:
    """Finalizes the certification process and packages the result."""
    is_organic = state.get("organic_certified", False)
    grade = state.get("corn_grade", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:certify_yield organic={is_organic} grade={grade}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("harvest_batch_id"),
            "certification": {
                "grade": grade,
                "moisture": state.get("moisture_percentage"),
                "organic": is_organic,
                "regulatory_standard": "USDA-7CFR-810"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_moisture)
_g.add_node("grade", grade_batch)
_g.add_node("certify", certify_yield)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "grade")
_g.add_edge("grade", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
