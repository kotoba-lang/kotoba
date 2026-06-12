# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12163701 — Chemical (segment 12).
Bespoke logic for handling chemical material metadata, purity verification, and safety assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12163701"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12163701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for "Chemical"
    composition_verified: bool
    hazard_classification: str
    safety_data_ready: bool
    purity_percentage: float


def inspect_composition(state: State) -> dict[str, Any]:
    """Inspects the chemical composition and verifies purity levels."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.0))
    verified = purity >= 95.0

    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition(purity={purity}%)"],
        "composition_verified": verified,
        "purity_percentage": purity
    }


def assess_safety(state: State) -> dict[str, Any]:
    """Evaluates hazard classifications and safety protocols based on substance data."""
    inp = state.get("input") or {}
    hazard_score = int(inp.get("hazard_score", 0))

    classification = "Low Risk"
    if hazard_score > 7:
        classification = "High Risk - Reactive"
    elif hazard_score > 3:
        classification = "Moderate Risk"

    return {
        "log": [f"{UNISPSC_CODE}:assess_safety(classification={classification})"],
        "hazard_classification": classification,
        "safety_data_ready": True
    }


def finalize_catalog(state: State) -> dict[str, Any]:
    """Finalizes the chemical catalog entry with verified safety and purity metadata."""
    is_verified = state.get("composition_verified", False)
    safety_class = state.get("hazard_classification", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalog"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "Certified" if is_verified else "Pending Review",
            "safety_profile": safety_class,
            "purity_level": f"{state.get('purity_percentage', 0.0)}%",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_composition", inspect_composition)
_g.add_node("assess_safety", assess_safety)
_g.add_node("finalize_catalog", finalize_catalog)

_g.add_edge(START, "inspect_composition")
_g.add_edge("inspect_composition", "assess_safety")
_g.add_edge("assess_safety", "finalize_catalog")
_g.add_edge("finalize_catalog", END)

graph = _g.compile()
