# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14120000 — Pulp (segment 14).

Bespoke logic for managing pulp production states, fiber refinement,
and moisture content validation within the LangGraph framework.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14120000"
UNISPSC_TITLE = "Pulp"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14120000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Pulp
    raw_material_type: str
    fiber_purity: float
    moisture_content: float
    bleaching_required: bool


def assess_input(state: State) -> dict[str, Any]:
    """Evaluates raw material source and determines if bleaching is necessary."""
    inp = state.get("input") or {}
    material = inp.get("material", "softwood")
    needs_bleach = inp.get("bleach", True)

    return {
        "log": [f"{UNISPSC_CODE}:assess_input"],
        "raw_material_type": material,
        "bleaching_required": needs_bleach,
        "fiber_purity": 0.0,
    }


def refine_fibers(state: State) -> dict[str, Any]:
    """Simulates chemical/mechanical refinement to increase fiber purity."""
    current_material = state.get("raw_material_type", "unknown")
    purity_gain = 0.95 if state.get("bleaching_required") else 0.85

    return {
        "log": [f"{UNISPSC_CODE}:refine_fibers"],
        "fiber_purity": purity_gain,
    }


def finalize_pulp_batch(state: State) -> dict[str, Any]:
    """Calculates final moisture levels and prepares the output manifest."""
    purity = state.get("fiber_purity", 0.0)
    final_moisture = 10.0  # target percentage for pulp sheets

    return {
        "log": [f"{UNISPSC_CODE}:finalize_pulp_batch"],
        "moisture_content": final_moisture,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "fiber_grade": "premium" if purity > 0.9 else "standard",
            "moisture": final_moisture,
            "status": "ready_for_mill",
        },
    }


_g = StateGraph(State)

_g.add_node("assess_input", assess_input)
_g.add_node("refine_fibers", refine_fibers)
_g.add_node("finalize_pulp_batch", finalize_pulp_batch)

_g.add_edge(START, "assess_input")
_g.add_edge("assess_input", "refine_fibers")
_g.add_edge("refine_fibers", "finalize_pulp_batch")
_g.add_edge("finalize_pulp_batch", END)

graph = _g.compile()
