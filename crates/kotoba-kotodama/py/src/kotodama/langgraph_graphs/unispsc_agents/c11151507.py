# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11151507 — Raw Material (segment 11).

Bespoke graph logic for handling raw material state transitions, including
inspection, grading, and inventory finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151507"
UNISPSC_TITLE = "Raw Material"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Raw Material
    material_type: str
    batch_id: str
    purity_grade: float
    origin_verified: bool


def inspect_material(state: State) -> dict[str, Any]:
    """Node: Inspect the raw material input for basic identification."""
    inp = state.get("input") or {}
    m_type = inp.get("material_type", "unclassified")
    b_id = inp.get("batch_id", "GEN-000")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_material -> {m_type} ({b_id})"],
        "material_type": m_type,
        "batch_id": b_id,
        "origin_verified": inp.get("verify_origin", False)
    }


def grade_batch(state: State) -> dict[str, Any]:
    """Node: Determine the purity grade based on batch data."""
    # Pure logic mock: higher grade if origin is verified
    purity = 0.98 if state.get("origin_verified") else 0.85
    return {
        "log": [f"{UNISPSC_CODE}:grade_batch -> purity_level: {purity}"],
        "purity_grade": purity
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Node: Consolidate state into the final result dictionary."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "inventory_data": {
                "batch": state.get("batch_id"),
                "type": state.get("material_type"),
                "grade": state.get("purity_grade"),
                "verified": state.get("origin_verified")
            },
            "success": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_material", inspect_material)
_g.add_node("grade_batch", grade_batch)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "inspect_material")
_g.add_edge("inspect_material", "grade_batch")
_g.add_edge("grade_batch", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
