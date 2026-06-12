# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11121803 — Magnesium (segment 11).

Bespoke logic for handling magnesium mineral material states including
purity verification, grading, and inventory logging within segment 11.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11121803"
UNISPSC_TITLE = "Magnesium"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11121803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    purity_percentage: float
    batch_id: str
    grade: str


def assay_sample(state: State) -> dict[str, Any]:
    """Inspects the input for material purity and batch identification."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.0))
    batch = str(inp.get("batch_id", "MG-TEMP-001"))
    return {
        "log": [f"{UNISPSC_CODE}:assay_sample: purity={purity}% batch={batch}"],
        "purity_percentage": purity,
        "batch_id": batch,
    }


def determine_grade(state: State) -> dict[str, Any]:
    """Assigns a commercial grade based on the verified purity level."""
    purity = state.get("purity_percentage", 0.0)
    if purity >= 99.9:
        grade = "High Purity (ASTM B92)"
    elif purity >= 90.0:
        grade = "Commercial Alloy Base"
    else:
        grade = "Recycle/Scrap"

    return {
        "log": [f"{UNISPSC_CODE}:determine_grade: assigned={grade}"],
        "grade": grade,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Finalizes the material state and prepares the inventory result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory: committed to ledger"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_id"),
            "grade": state.get("grade"),
            "status": "ready_for_distribution",
        },
    }


_g = StateGraph(State)

_g.add_node("assay_sample", assay_sample)
_g.add_node("determine_grade", determine_grade)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "assay_sample")
_g.add_edge("assay_sample", "determine_grade")
_g.add_edge("determine_grade", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
