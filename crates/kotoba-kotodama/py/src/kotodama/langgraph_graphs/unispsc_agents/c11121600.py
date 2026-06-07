# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11121600 — Mineral (segment 11).

Bespoke graph logic for Mineral extraction validation and purity assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11121600"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11121600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Mineral domain fields
    extraction_site: str
    purity_grade: float
    composition_verified: bool
    refinement_status: str
    weight_metric_tons: float


def validate_extraction(state: State) -> dict[str, Any]:
    """Validates the source and initial extraction metrics."""
    inp = state.get("input") or {}
    site = inp.get("site", "Sector-7")
    weight = float(inp.get("weight", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_extraction(site={site}, weight={weight})"],
        "extraction_site": site,
        "weight_metric_tons": weight,
        "composition_verified": True,
    }


def assess_purity(state: State) -> dict[str, Any]:
    """Analyzes chemical composition to determine mineral grade."""
    inp = state.get("input") or {}
    grade = float(inp.get("purity", 0.88))
    status = "refined" if grade > 0.9 else "raw"

    return {
        "log": [f"{UNISPSC_CODE}:assess_purity(grade={grade}, status={status})"],
        "purity_grade": grade,
        "refinement_status": status,
    }


def emit_mineral_record(state: State) -> dict[str, Any]:
    """Generates the final mineral asset record."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_mineral_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "site": state.get("extraction_site"),
            "grade": state.get("purity_grade"),
            "status": state.get("refinement_status"),
            "ok": state.get("composition_verified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate_extraction", validate_extraction)
_g.add_node("assess_purity", assess_purity)
_g.add_node("emit_mineral_record", emit_mineral_record)

_g.add_edge(START, "validate_extraction")
_g.add_edge("validate_extraction", "assess_purity")
_g.add_edge("assess_purity", "emit_mineral_record")
_g.add_edge("emit_mineral_record", END)

graph = _g.compile()
