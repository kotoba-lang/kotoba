# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151702 — Feed Grain (segment 10).

Bespoke logic for managing feed grain quality control, moisture validation,
and protein grading for distribution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151702"
UNISPSC_TITLE = "Feed Grain"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    grain_type: str
    moisture_percentage: float
    protein_content: float
    lot_id: str
    quality_certified: bool


def inspect_intake(state: State) -> dict[str, Any]:
    """Inspects the raw feed grain intake and extracts base metrics."""
    inp = state.get("input") or {}
    grain_type = inp.get("grain_type", "yellow_corn")
    moisture = float(inp.get("moisture_level", 13.5))
    lot = inp.get("lot_id", "FG-BATCH-001")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_intake - Batch {lot} identified"],
        "grain_type": grain_type,
        "moisture_percentage": moisture,
        "lot_id": lot,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyzes the protein levels and determines quality certification status."""
    inp = state.get("input") or {}
    protein = float(inp.get("protein_analysis", 8.5))
    moisture = state.get("moisture_percentage", 0.0)

    # Standard feed grain moisture should be below 15%
    certified = (moisture < 15.0) and (protein >= 7.5)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition - Certified: {certified}"],
        "protein_content": protein,
        "quality_certified": certified,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Finalizes the grain state and emits the result record."""
    certified = state.get("quality_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest - {'Accepted' if certified else 'Flagged'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "lot_id": state.get("lot_id"),
            "grain": state.get("grain_type"),
            "metrics": {
                "moisture": state.get("moisture_percentage"),
                "protein": state.get("protein_content")
            },
            "did": UNISPSC_DID,
            "certified": certified,
            "disposition": "approved" if certified else "quarantine"
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_intake", inspect_intake)
_g.add_node("analyze_composition", analyze_composition)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "inspect_intake")
_g.add_edge("inspect_intake", "analyze_composition")
_g.add_edge("analyze_composition", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
