# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121805 — Industrial Paper Materials (segment 14).

Bespoke logic for paper product specification verification and grade classification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121805"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121805"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    porosity_microns: float
    gsm_weight: float
    grade_rating: str
    compliance_passed: bool


def inspect_paper_specs(state: State) -> dict[str, Any]:
    """Inspects physical specifications of the paper material."""
    inp = state.get("input") or {}
    porosity = float(inp.get("porosity", 10.0))
    gsm = float(inp.get("gsm", 80.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_paper_specs"],
        "porosity_microns": porosity,
        "gsm_weight": gsm,
    }


def analyze_grade(state: State) -> dict[str, Any]:
    """Analyzes and assigns a quality grade based on porosity and weight."""
    porosity = state.get("porosity_microns", 10.0)
    gsm = state.get("gsm_weight", 80.0)

    if porosity < 5 and gsm > 100:
        grade = "Premium Industrial"
    elif porosity < 15:
        grade = "Standard Filter"
    else:
        grade = "General Utility"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_grade"],
        "grade_rating": grade,
        "compliance_passed": True
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Finalizes the industrial certification for the paper product."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "grade": state.get("grade_rating"),
            "compliance": state.get("compliance_passed"),
            "certified_at": "2026-05-23"
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_paper_specs)
_g.add_node("analyze", analyze_grade)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
