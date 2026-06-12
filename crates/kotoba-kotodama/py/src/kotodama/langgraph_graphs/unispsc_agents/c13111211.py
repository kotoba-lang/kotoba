# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111211 — Crude Oil (segment 13).

This agent handles state transitions for crude oil assay analysis,
grade classification, and valuation logic based on physical properties.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111211"
UNISPSC_TITLE = "Crude Oil"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111211"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Crude Oil
    api_gravity: float
    sulfur_content: float
    viscosity: float
    grade: str
    is_export_ready: bool


def assay_analysis(state: State) -> dict[str, Any]:
    """Analyzes the physical properties to determine the oil grade."""
    inp = state.get("input") or {}
    api = float(inp.get("api_gravity", 30.0))
    sulfur = float(inp.get("sulfur_content", 0.5))

    # Classification logic: Light Sweet vs Heavy Sour
    if api > 31.1:
        grade_type = "Light"
    elif api > 22.3:
        grade_type = "Medium"
    else:
        grade_type = "Heavy"

    sweetness = "Sweet" if sulfur < 0.5 else "Sour"
    grade = f"{grade_type} {sweetness}"

    return {
        "log": [f"{UNISPSC_CODE}:assay_analysis: classified as {grade}"],
        "api_gravity": api,
        "sulfur_content": sulfur,
        "grade": grade
    }


def valuation_engine(state: State) -> dict[str, Any]:
    """Calculates valuation adjustments based on grade classification."""
    grade = state.get("grade", "Unknown")
    api = state.get("api_gravity", 30.0)

    # Hypothetical adjustment relative to a benchmark
    adjustment = (api - 31.1) * 0.15

    return {
        "log": [f"{UNISPSC_CODE}:valuation_engine: calculated adjustment of {adjustment:.2f}"],
        "result": {
            "valuation_adjustment": adjustment,
            "benchmark_alignment": "WTI" if api > 30 else "Brent"
        }
    }


def export_validation(state: State) -> dict[str, Any]:
    """Verifies if the specifications meet export pipeline standards."""
    api = state.get("api_gravity", 0.0)
    sulfur = state.get("sulfur_content", 10.0)

    # Example export criteria
    is_ready = api >= 10.0 and sulfur <= 3.0

    res = state.get("result", {})
    res.update({
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "is_export_ready": is_ready,
        "ok": True
    })

    return {
        "log": [f"{UNISPSC_CODE}:export_validation: ready={is_ready}"],
        "is_export_ready": is_ready,
        "result": res
    }


_g = StateGraph(State)
_g.add_node("assay_analysis", assay_analysis)
_g.add_node("valuation_engine", valuation_engine)
_g.add_node("export_validation", export_validation)

_g.add_edge(START, "assay_analysis")
_g.add_edge("assay_analysis", "valuation_engine")
_g.add_edge("valuation_engine", "export_validation")
_g.add_edge("export_validation", END)

graph = _g.compile()
