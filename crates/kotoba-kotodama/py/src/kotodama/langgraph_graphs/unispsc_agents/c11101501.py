# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101501 — Ore (segment 11).

Bespoke graph logic for handling mineral ore data, including purity assessment
and extraction classification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101501"
UNISPSC_TITLE = "Ore"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101501"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Ore
    ore_type: str  # e.g., "Iron", "Copper", "Bauxite"
    purity_grade: float  # percentage of mineral content
    extraction_method: str  # "Open-pit", "Underground", "Dredging"
    is_refined: bool
    batch_id: str


def analyze_specimen(state: State) -> dict[str, Any]:
    """Node: Validate input and identify the ore characteristics."""
    inp = state.get("input") or {}
    ore_type = inp.get("ore_type", "Unknown Mineral")
    purity = float(inp.get("purity", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specimen -> {ore_type} at {purity}%"],
        "ore_type": ore_type,
        "purity_grade": purity,
        "batch_id": inp.get("batch_id", "TEMP-BATCH-000")
    }


def grade_purity(state: State) -> dict[str, Any]:
    """Node: Determine the quality grade based on purity percentage."""
    purity = state.get("purity_grade", 0.0)
    is_refined = purity > 90.0

    extraction = "Standard"
    if purity < 20.0:
        extraction = "Low-yield Refinement Required"

    return {
        "log": [f"{UNISPSC_CODE}:grade_purity -> Refined: {is_refined}"],
        "is_refined": is_refined,
        "extraction_method": extraction
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Node: Compile the final result for the Ore actor."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "ore_type": state.get("ore_type"),
                "purity": f"{state.get('purity_grade')}%",
                "is_refined": state.get("is_refined"),
                "batch_id": state.get("batch_id"),
                "extraction": state.get("extraction_method")
            },
            "status": "Verified" if state.get("purity_grade", 0) > 0 else "Incomplete"
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_specimen)
_g.add_node("grade", grade_purity)
_g.add_node("manifest", generate_manifest)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "grade")
_g.add_edge("grade", "manifest")
_g.add_edge("manifest", END)

graph = _g.compile()
