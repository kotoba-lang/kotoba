# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352205 — Titanium (segment 12).

Bespoke logic for titanium material tracking, assay simulation, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352205"
UNISPSC_TITLE = "Titanium"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352205"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Titanium domain
    purity_grade: str
    alloy_composition: dict[str, float]
    certification_status: str
    batch_id: str


def inspect_batch(state: State) -> dict[str, Any]:
    """Inspects the incoming batch metadata for titanium stock."""
    inp = state.get("input") or {}
    batch_id = inp.get("batch_id", "T-BATCH-DEFAULT")
    purity = inp.get("purity", "Grade 2")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_batch:{batch_id}"],
        "batch_id": batch_id,
        "purity_grade": purity,
    }


def assay_purity(state: State) -> dict[str, Any]:
    """Simulates chemical assay to determine alloy composition."""
    grade = state.get("purity_grade", "Grade 2")
    # Grade 2 is commercially pure; Grade 5 is Ti-6Al-4V (aerospace)
    if grade == "Grade 5":
        composition = {"Ti": 90.0, "Al": 6.0, "V": 4.0}
    else:
        # Standard commercially pure titanium Grade 2
        composition = {"Ti": 99.2, "Fe": 0.30, "O": 0.25, "N": 0.03}

    return {
        "log": [f"{UNISPSC_CODE}:assay_purity:{grade}"],
        "alloy_composition": composition,
    }


def certify_material(state: State) -> dict[str, Any]:
    """Generates compliance certificates based on alloy composition and grade."""
    comp = state.get("alloy_composition", {})
    batch = state.get("batch_id")
    grade = state.get("purity_grade")

    # Determine certification type based on properties
    is_aerospace_grade = comp.get("Al", 0) == 6.0 and comp.get("V", 0) == 4.0
    cert = "AMS-4911-L" if is_aerospace_grade else "ASTM-B265-CP"

    return {
        "log": [f"{UNISPSC_CODE}:certify_material:{cert}"],
        "certification_status": cert,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "material_data": {
                "batch_id": batch,
                "grade": grade,
                "composition": comp,
                "certification": cert,
                "quality_verified": True
            }
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_batch)
_g.add_node("assay", assay_purity)
_g.add_node("certify", certify_material)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "assay")
_g.add_edge("assay", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
