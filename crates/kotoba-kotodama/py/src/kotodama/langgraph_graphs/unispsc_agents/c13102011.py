# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102011 — Abrasive.
Bespoke logic for grading and verifying abrasive materials.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102011"
UNISPSC_TITLE = "Abrasive"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102011"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Abrasive
    grit_rating: int
    material_composition: str
    bonding_type: str
    safety_compliance: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Inspects the input for material and safety specifications."""
    inp = state.get("input") or {}
    composition = inp.get("material", "unknown")
    compliance = inp.get("safety_check", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "material_composition": composition,
        "safety_compliance": compliance,
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Determines the grit rating and bonding characteristics based on composition."""
    composition = state.get("material_composition", "unknown")

    # Simple logic to simulate abrasive grading
    grit = 80  # Default medium grit
    if "diamond" in composition.lower():
        grit = 1200
    elif "silicon" in composition.lower():
        grit = 400

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "grit_rating": grit,
        "bonding_type": "Resin" if grit > 100 else "Vitrified",
    }


def finalize_catalog(state: State) -> dict[str, Any]:
    """Prepares the final result for the Abrasive actor."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalog"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "grit": state.get("grit_rating"),
                "material": state.get("material_composition"),
                "bonding": state.get("bonding_type"),
                "safe": state.get("safety_compliance"),
            },
            "status": "verified" if state.get("safety_compliance") else "pending_safety",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("analyze", analyze_performance)
_g.add_node("finalize", finalize_catalog)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
