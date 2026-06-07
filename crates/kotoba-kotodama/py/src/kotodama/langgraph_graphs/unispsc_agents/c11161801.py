# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11161801 — Mineral (segment 11).

Bespoke graph logic for mineral assay analysis and classification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11161801"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11161801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Mineral-specific domain state
    assay_report: dict[str, float]
    geological_classification: str
    impurity_check_passed: bool
    refining_required: bool


def analyze_assay(state: State) -> dict[str, Any]:
    """Analyzes the mineral assay for composition and impurities."""
    inp = state.get("input") or {}
    assay = inp.get("assay", {"purity": 0.88, "silica": 0.04})

    # Logic: minerals with silica > 0.1 fail base purity check
    impurity_ok = assay.get("silica", 0) < 0.1

    return {
        "log": [f"{UNISPSC_CODE}:analyze_assay"],
        "assay_report": assay,
        "impurity_check_passed": impurity_ok,
        "refining_required": assay.get("purity", 0) < 0.95
    }


def classify_mineral(state: State) -> dict[str, Any]:
    """Classifies the mineral based on its assay data."""
    assay = state.get("assay_report", {})
    purity = assay.get("purity", 0)

    if purity > 0.98:
        grade = "Refined High-Purity"
    elif purity > 0.85:
        grade = "Industrial Standard"
    else:
        grade = "Raw Extraction"

    return {
        "log": [f"{UNISPSC_CODE}:classify_mineral"],
        "geological_classification": grade
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Prepares the final result and record for the Mineral actor."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "classification": state.get("geological_classification"),
            "impurity_verified": state.get("impurity_check_passed"),
            "processing_path": "Refine" if state.get("refining_required") else "Direct Use",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_assay", analyze_assay)
_g.add_node("classify_mineral", classify_mineral)
_g.add_node("finalize_record", finalize_record)

_g.add_edge(START, "analyze_assay")
_g.add_edge("analyze_assay", "classify_mineral")
_g.add_edge("classify_mineral", "finalize_record")
_g.add_edge("finalize_record", END)

graph = _g.compile()
