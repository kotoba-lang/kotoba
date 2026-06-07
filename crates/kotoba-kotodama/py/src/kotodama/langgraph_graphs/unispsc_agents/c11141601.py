# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11141601 — Mineral Proc (segment 11).

Bespoke logic for mineral processing workflows, including feed validation,
refining simulation, and quality assurance metrics for mineral outputs.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11141601"
UNISPSC_TITLE = "Mineral Proc"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11141601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Mineral Processing
    ore_grade: float
    processing_method: str
    purity_attained: float
    is_compliant: bool


def validate_feed(state: State) -> dict[str, Any]:
    """Validates the input mineral feed characteristics and compliance."""
    inp = state.get("input") or {}
    grade = float(inp.get("ore_grade", 0.12))
    method = str(inp.get("method", "gravity_separation"))

    # Basic compliance check based on minimum feed grade
    compliant = grade >= 0.05

    return {
        "log": [f"{UNISPSC_CODE}:validate_feed - grade={grade}, compliant={compliant}"],
        "ore_grade": grade,
        "processing_method": method,
        "is_compliant": compliant,
    }


def refine_minerals(state: State) -> dict[str, Any]:
    """Simulates the refining/extraction process based on the selected method."""
    grade = state.get("ore_grade", 0.0)
    method = state.get("processing_method", "standard")

    # Efficiency varies by processing method
    efficiency_factor = 0.95 if "flotation" in method else 0.85
    purity = min(0.999, grade * efficiency_factor * 8.0)

    return {
        "log": [f"{UNISPSC_CODE}:refine_minerals - method={method}, purity={purity:.4f}"],
        "purity_attained": purity,
    }


def quality_assurance(state: State) -> dict[str, Any]:
    """Performs final quality checks and emits the processing result."""
    purity = state.get("purity_attained", 0.0)
    compliant = state.get("is_compliant", False)

    # Success requires both initial compliance and meeting purity thresholds
    success = compliant and purity > 0.80

    return {
        "log": [f"{UNISPSC_CODE}:quality_assurance - success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "final_purity": purity,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_feed", validate_feed)
_g.add_node("refine_minerals", refine_minerals)
_g.add_node("quality_assurance", quality_assurance)

_g.add_edge(START, "validate_feed")
_g.add_edge("validate_feed", "refine_minerals")
_g.add_edge("refine_minerals", "quality_assurance")
_g.add_edge("quality_assurance", END)

graph = _g.compile()
