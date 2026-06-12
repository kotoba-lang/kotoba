# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101606 — Mineral Chem (segment 11).

Bespoke graph logic for Mineral Chem chemical analysis and assay verification.
This agent processes chemical specifications of mineral-derived substances,
verifies purity thresholds, and generates a structured assay result.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101606"
UNISPSC_TITLE = "Mineral Chem"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    chemical_formula: str
    purity_level: float
    is_industrial_grade: bool
    batch_reference_id: str


def analyze_composition(state: State) -> dict[str, Any]:
    """Extracts mineral composition and chemical identification from input."""
    inp = state.get("input") or {}
    formula = inp.get("formula", "N/A")
    batch_id = inp.get("batch_id", "GEN-M-000")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition: {formula}"],
        "chemical_formula": formula,
        "batch_reference_id": batch_id,
    }


def verify_purity(state: State) -> dict[str, Any]:
    """Checks the purity level against standard industrial mineral requirements."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.0))
    # Standard mineral chem industrial grade threshold often set at 94%
    industrial_grade = purity >= 0.94

    return {
        "log": [f"{UNISPSC_CODE}:verify_purity: level={purity}"],
        "purity_level": purity,
        "is_industrial_grade": industrial_grade,
    }


def emit_assay_report(state: State) -> dict[str, Any]:
    """Generates the final mineral chemical result and DID metadata."""
    purity = state.get("purity_level", 0.0)
    is_ok = state.get("is_industrial_grade", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_assay_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_reference_id"),
            "formula": state.get("chemical_formula"),
            "purity": f"{purity * 100:.2f}%",
            "verified_grade": "Industrial" if is_ok else "Sub-standard",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_composition)
_g.add_node("verify", verify_purity)
_g.add_node("emit", emit_assay_report)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
