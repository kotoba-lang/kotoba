# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12131604 — Nickel Processing.
This bespoke graph handles the refinement and quality control steps for nickel ore processing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12131604"
UNISPSC_TITLE = "Nickel Processing"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12131604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Nickel Processing
    ore_grade: float
    refinement_method: str
    purity_level: float
    batch_tracking_id: str
    is_certified: bool


def assay_ore(state: State) -> dict[str, Any]:
    """Analyze the input ore quality and determine the starting grade."""
    inp = state.get("input") or {}
    grade = inp.get("ore_grade", 0.02)  # Default to 2% if not specified
    batch_id = inp.get("batch_id", "B-000")

    return {
        "log": [f"{UNISPSC_CODE}:assay_ore_started"],
        "ore_grade": grade,
        "batch_tracking_id": batch_id,
        "refinement_method": "Pyrometallurgical" if grade > 0.015 else "Hydrometallurgical"
    }


def refine_nickel(state: State) -> dict[str, Any]:
    """Apply refinement logic to increase purity level."""
    method = state.get("refinement_method", "Unknown")
    # Simulate refinement increasing purity to standard levels (99.8%+)
    return {
        "log": [f"{UNISPSC_CODE}:refining_via_{method}"],
        "purity_level": 99.92,
        "is_certified": True
    }


def finalize_batch(state: State) -> dict[str, Any]:
    """Generate final result and close out the processing batch."""
    purity = state.get("purity_level", 0.0)
    batch_id = state.get("batch_tracking_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:batch_finalized"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "batch_id": batch_id,
            "final_purity": f"{purity}%",
            "status": "Ready for Shipment",
            "did": UNISPSC_DID,
            "ok": state.get("is_certified", False),
        },
    }


_g = StateGraph(State)

_g.add_node("assay_ore", assay_ore)
_g.add_node("refine_nickel", refine_nickel)
_g.add_node("finalize_batch", finalize_batch)

_g.add_edge(START, "assay_ore")
_g.add_edge("assay_ore", "refine_nickel")
_g.add_edge("refine_nickel", "finalize_batch")
_g.add_edge("finalize_batch", END)

graph = _g.compile()
