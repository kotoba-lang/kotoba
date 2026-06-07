# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10121804 — Gear Oil (segment 10).

Bespoke LangGraph implementation for Gear Oil specification and verification.
This agent handles viscosity grading, API GL rating validation, and
base oil classification for industrial and automotive gear applications.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10121804"
UNISPSC_TITLE = "Gear Oil"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10121804"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Gear Oil
    viscosity_grade: str
    gl_rating: str
    base_oil_type: str
    is_hypoid_compatible: bool


def analyze_specs(state: State) -> dict[str, Any]:
    """Extract and analyze gear oil specifications from input."""
    inp = state.get("input") or {}
    viscosity = inp.get("viscosity", "80W-90")
    rating = inp.get("rating", "GL-5")
    base = inp.get("base", "mineral")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specs -> {viscosity}, {rating}"],
        "viscosity_grade": viscosity,
        "gl_rating": rating,
        "base_oil_type": base,
    }


def verify_compatibility(state: State) -> dict[str, Any]:
    """Verify if the oil is compatible with high-load hypoid gears."""
    rating = state.get("gl_rating", "")
    # API GL-5 is typically required for hypoid gears due to EP additives
    is_hypoid = rating.upper() == "GL-5"

    return {
        "log": [f"{UNISPSC_CODE}:verify_compatibility -> hypoid_ok={is_hypoid}"],
        "is_hypoid_compatible": is_hypoid,
    }


def formulate_recommendation(state: State) -> dict[str, Any]:
    """Generate the final recommendation based on analyzed specs."""
    viscosity = state.get("viscosity_grade")
    rating = state.get("gl_rating")
    is_hypoid = state.get("is_hypoid_compatible")

    status = "Approved" if is_hypoid else "Restricted (Non-Hypoid Only)"

    return {
        "log": [f"{UNISPSC_CODE}:formulate_recommendation"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "viscosity": viscosity,
                "rating": rating,
                "hypoid_compatible": is_hypoid,
            },
            "status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_specs", analyze_specs)
_g.add_node("verify_compatibility", verify_compatibility)
_g.add_node("formulate_recommendation", formulate_recommendation)

_g.add_edge(START, "analyze_specs")
_g.add_edge("analyze_specs", "verify_compatibility")
_g.add_edge("verify_compatibility", "formulate_recommendation")
_g.add_edge("formulate_recommendation", END)

graph = _g.compile()
