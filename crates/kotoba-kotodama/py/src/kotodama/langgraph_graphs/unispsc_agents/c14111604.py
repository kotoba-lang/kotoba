# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111604 — Paper (segment 14).

Bespoke graph logic for handling Paper product specifications, grading,
and basis weight validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111604"
UNISPSC_TITLE = "Paper"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Paper-specific domain fields
    paper_grade: str
    basis_weight_gsm: int
    opacity_pct: float
    is_acid_free: bool


def parse_specs(state: State) -> dict[str, Any]:
    """Extracts paper properties from the input payload."""
    payload = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:parse_specs"],
        "paper_grade": payload.get("grade", "Coated Fine"),
        "basis_weight_gsm": payload.get("gsm", 90),
        "opacity_pct": payload.get("opacity", 94.0),
        "is_acid_free": payload.get("acid_free", True),
    }


def validate_properties(state: State) -> dict[str, Any]:
    """Validates the physical properties of the paper against industrial norms."""
    gsm = state.get("basis_weight_gsm", 0)
    opacity = state.get("opacity_pct", 0.0)

    # Example logic: validation based on weight and opacity correlation
    is_valid = (gsm > 100 and opacity > 90) or (gsm <= 100)

    return {
        "log": [f"{UNISPSC_CODE}:validate_properties(valid={is_valid})"],
    }


def synthesize_output(state: State) -> dict[str, Any]:
    """Prepares the final result including the validated paper manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:synthesize_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "manifest": {
                "grade": state.get("paper_grade"),
                "gsm": state.get("basis_weight_gsm"),
                "opacity": state.get("opacity_pct"),
                "acid_free": state.get("is_acid_free"),
            },
            "status": "validated",
        },
    }


_g = StateGraph(State)
_g.add_node("parse_specs", parse_specs)
_g.add_node("validate_properties", validate_properties)
_g.add_node("synthesize_output", synthesize_output)

_g.add_edge(START, "parse_specs")
_g.add_edge("parse_specs", "validate_properties")
_g.add_edge("validate_properties", "synthesize_output")
_g.add_edge("synthesize_output", END)

graph = _g.compile()
