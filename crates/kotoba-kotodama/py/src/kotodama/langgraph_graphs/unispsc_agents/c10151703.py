# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151703 — Soybean (segment 10).

This bespoke LangGraph implementation handles state transitions for soybean
commodity processing, including moisture validation, protein content grading,
and shipment certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151703"
UNISPSC_TITLE = "Soybean"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Soybean
    moisture_percentage: float
    protein_index: float
    usda_grade: str
    is_ready_for_export: bool


def assess_quality(state: State) -> dict[str, Any]:
    """Inspects moisture and protein levels from input data."""
    inp = state.get("input") or {}
    moisture = float(inp.get("moisture", 13.0))
    protein = float(inp.get("protein", 35.0))

    log_entry = f"{UNISPSC_CODE}:assess_quality (Moisture: {moisture}%, Protein: {protein}%)"

    return {
        "log": [log_entry],
        "moisture_percentage": moisture,
        "protein_index": protein,
    }


def determine_grade(state: State) -> dict[str, Any]:
    """Assigns a USDA-equivalent grade based on soybean metrics."""
    moisture = state.get("moisture_percentage", 0.0)
    protein = state.get("protein_index", 0.0)

    # Simple logic: moisture > 14% or low protein results in lower grade
    if moisture > 14.0:
        grade = "No. 3 Yellow"
    elif protein > 36.0:
        grade = "No. 1 Yellow"
    else:
        grade = "No. 2 Yellow"

    return {
        "log": [f"{UNISPSC_CODE}:determine_grade ({grade})"],
        "usda_grade": grade,
        "is_ready_for_export": moisture <= 13.5 and grade != "No. 3 Yellow",
    }


def finalize_lot(state: State) -> dict[str, Any]:
    """Finalizes the commodity record and emits the result."""
    grade = state.get("usda_grade", "Unknown")
    ready = state.get("is_ready_for_export", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_lot (Export Ready: {ready})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certification": {
                "grade": grade,
                "export_status": "APPROVED" if ready else "PENDING_DRYING",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("assess_quality", assess_quality)
_g.add_node("determine_grade", determine_grade)
_g.add_node("finalize_lot", finalize_lot)

_g.add_edge(START, "assess_quality")
_g.add_edge("assess_quality", "determine_grade")
_g.add_edge("determine_grade", "finalize_lot")
_g.add_edge("finalize_lot", END)

graph = _g.compile()
