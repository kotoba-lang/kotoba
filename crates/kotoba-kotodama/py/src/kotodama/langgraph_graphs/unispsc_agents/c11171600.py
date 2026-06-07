# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11171600 — Mineral Chemical (segment 11).

Bespoke graph logic for managing mineral chemical state transitions,
purity verification, and safety protocol compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11171600"
UNISPSC_TITLE = "Mineral Chemical"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11171600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Mineral Chemical
    purity_grade: str
    composition_analysis: dict[str, float]
    safety_data_verified: bool
    handling_instructions: list[str]


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyzes the mineral chemical composition and determines the grade."""
    inp = state.get("input") or {}
    # Simulate extraction/analysis of composition data from input or defaults
    comp = inp.get("composition", {"pure_content": 0.985, "trace_elements": 0.015})

    purity = comp.get("pure_content", 0.0)
    if purity >= 0.99:
        grade = "Analytical Reagent"
    elif purity >= 0.95:
        grade = "Technical Grade"
    else:
        grade = "Raw Mineral"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition -> {grade}"],
        "purity_grade": grade,
        "composition_analysis": comp,
    }


def verify_safety_protocols(state: State) -> dict[str, Any]:
    """Ensures safety handling protocols are matched to the chemical grade."""
    grade = state.get("purity_grade", "Raw Mineral")
    instructions = ["Observe standard MSDS"]

    if grade == "Analytical Reagent":
        instructions.append("Sealed atmosphere storage")
        instructions.append("No skin contact")
    elif grade == "Technical Grade":
        instructions.append("Ventilated storage")

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_protocols"],
        "safety_data_verified": True,
        "handling_instructions": instructions,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Produces the final result manifest for the mineral chemical agent."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "manifest": {
                "purity_grade": state.get("purity_grade"),
                "composition": state.get("composition_analysis"),
                "safety_verified": state.get("safety_data_verified"),
                "handling": state.get("handling_instructions"),
            },
            "status": "certified",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_composition)
_g.add_node("verify", verify_safety_protocols)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
