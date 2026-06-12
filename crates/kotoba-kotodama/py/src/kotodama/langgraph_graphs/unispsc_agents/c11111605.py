# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11111605 — Carbon (segment 11).

Bespoke graph logic for Carbon classification and purity assessment.
Handles allotrope identification, grade determination, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11111605"
UNISPSC_TITLE = "Carbon"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11111605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Carbon (Minerals)
    allotrope: str
    purity_percent: float
    grade: str
    is_certified: bool


def analyze_composition(state: State) -> dict[str, Any]:
    """Identify the allotrope and purity level of the carbon sample."""
    inp = state.get("input") or {}
    # Default to industrial graphite if not specified
    allotrope = str(inp.get("allotrope", "graphite")).lower()
    purity = float(inp.get("purity", 99.5))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition (allotrope={allotrope}, purity={purity}%)"],
        "allotrope": allotrope,
        "purity_percent": purity,
    }


def assess_grade(state: State) -> dict[str, Any]:
    """Determine the commercial grade based on purity and structure."""
    allotrope = state.get("allotrope", "unknown")
    purity = state.get("purity_percent", 0.0)

    if allotrope == "diamond":
        grade = "gemstone" if purity > 99.9 else "industrial_abrasive"
    elif allotrope == "fullerene" or allotrope == "graphene":
        grade = "research_grade"
    elif purity > 99.99:
        grade = "ultra_high_purity"
    elif purity > 99.0:
        grade = "commercial_grade"
    else:
        grade = "metallurgical_coke"

    return {
        "log": [f"{UNISPSC_CODE}:assess_grade (grade={grade})"],
        "grade": grade,
    }


def certify_mineral(state: State) -> dict[str, Any]:
    """Issue a digital certification for the analyzed Carbon batch."""
    grade = state.get("grade", "unknown")
    purity = state.get("purity_percent", 0.0)

    # Simple logic to verify if it meets minimum standards for its claimed segment
    certified = purity > 85.0

    return {
        "log": [f"{UNISPSC_CODE}:certify_mineral (certified={certified})"],
        "is_certified": certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "allotrope": state.get("allotrope"),
                "purity": purity,
                "commercial_grade": grade,
                "certification_status": "verified" if certified else "rejected"
            },
            "ok": certified,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_composition)
_g.add_node("grade", assess_grade)
_g.add_node("certify", certify_mineral)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "grade")
_g.add_edge("grade", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
