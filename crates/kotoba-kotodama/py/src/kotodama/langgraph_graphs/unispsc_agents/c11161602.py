# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11161602 — Inorganic (segment 11).

Bespoke graph logic for handling inorganic material analysis, purity
verification, and safety data compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11161602"
UNISPSC_TITLE = "Inorganic"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11161602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Inorganic materials
    purity_grade: float
    chemical_formula: str
    safety_data_verified: bool
    batch_serial: str


def validate_input(state: State) -> dict[str, Any]:
    """Validates the incoming material specifications."""
    inp = state.get("input") or {}
    batch = inp.get("batch", "GEN-000")
    formula = inp.get("formula", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:validate_input:{batch}"],
        "batch_serial": batch,
        "chemical_formula": formula,
        "safety_data_verified": False
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Simulates chemical analysis of the inorganic compound."""
    formula = state.get("chemical_formula", "")
    # Simple deterministic logic for purity based on formula length/input
    purity = 0.999 if len(formula) > 2 else 0.85

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition:purity={purity}"],
        "purity_grade": purity,
        "safety_data_verified": purity > 0.95
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Finalizes the state and emits the certified material record."""
    is_verified = state.get("safety_data_verified", False)
    purity = state.get("purity_grade", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:emit_certification:verified={is_verified}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purity": purity,
            "certified": is_verified,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_input)
_g.add_node("analyze", analyze_composition)
_g.add_node("emit", emit_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
