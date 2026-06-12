# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242304 — Machine Spec (segment 23).
Bespoke logic for machine specification validation and technical assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242304"
UNISPSC_TITLE = "Machine Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242304"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Machine Spec assessment
    tech_specs: dict[str, Any]
    is_valid_spec: bool
    tolerance_results: dict[str, bool]
    safety_certified: bool


def validate_spec_completeness(state: State) -> dict[str, Any]:
    """Checks if the provided machine specification contains required fields."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})

    # Requirement: Must have 'model' and 'operating_range' defined
    is_valid = bool(specs.get("model")) and "operating_range" in specs

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec_completeness"],
        "tech_specs": specs,
        "is_valid_spec": is_valid,
    }


def analyze_tolerances(state: State) -> dict[str, Any]:
    """Analyzes the technical tolerances against standard industrial benchmarks."""
    specs = state.get("tech_specs") or {}
    op_range = specs.get("operating_range", {})

    # Mock analysis: check if max temperature is within safe limits for segment 23 machinery
    max_temp = op_range.get("max_temp_c", 0)
    safety_certified = 0 < max_temp <= 800

    results = {
        "thermal_compliance": safety_certified,
        "vibration_check": specs.get("vibration_level", 0) < 5.0,
    }

    return {
        "log": [f"{UNISPSC_CODE}:analyze_tolerances"],
        "tolerance_results": results,
        "safety_certified": safety_certified and results["vibration_check"],
    }


def finalize_assessment(state: State) -> dict[str, Any]:
    """Compiles the final machine specification assessment result."""
    valid = state.get("is_valid_spec", False)
    safe = state.get("safety_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_assessment"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "APPROVED" if valid and safe else "REJECTED",
            "did": UNISPSC_DID,
            "segment": UNISPSC_SEGMENT,
            "ok": valid and safe,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_spec_completeness)
_g.add_node("analyze", analyze_tolerances)
_g.add_node("finalize", finalize_assessment)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
