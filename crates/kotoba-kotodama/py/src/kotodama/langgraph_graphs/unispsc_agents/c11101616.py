# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101616 — Mineral (segment 11).

Bespoke graph for mineral property analysis, quality validation, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101616"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101616"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Mineral processing
    mineral_name: str
    chemical_formula: str
    mohs_hardness: float
    is_industrial_grade: bool
    inspection_passed: bool


def inspect_properties(state: State) -> dict[str, Any]:
    """Extracts mineral properties from input data and log entry."""
    inp = state.get("input") or {}
    name = inp.get("name", "Unknown Mineral")
    formula = inp.get("formula", "N/A")
    hardness = float(inp.get("hardness", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_properties:{name}"],
        "mineral_name": name,
        "chemical_formula": formula,
        "mohs_hardness": hardness,
    }


def validate_quality(state: State) -> dict[str, Any]:
    """Determines if the mineral meets industrial grade requirements based on hardness."""
    hardness = state.get("mohs_hardness", 0.0)
    # Logic: Minerals with hardness >= 5.0 are considered durable enough for industrial use
    is_industrial = hardness >= 5.0
    passed = hardness > 0.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_quality:industrial={is_industrial}"],
        "is_industrial_grade": is_industrial,
        "inspection_passed": passed,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final result and record for the mineral sample."""
    is_ok = state.get("inspection_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "name": state.get("mineral_name"),
                "formula": state.get("chemical_formula"),
                "hardness": state.get("mohs_hardness"),
                "industrial_grade": state.get("is_industrial_grade"),
            },
            "certified": is_ok,
            "status": "completed",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_properties", inspect_properties)
_g.add_node("validate_quality", validate_quality)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "inspect_properties")
_g.add_edge("inspect_properties", "validate_quality")
_g.add_edge("validate_quality", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
