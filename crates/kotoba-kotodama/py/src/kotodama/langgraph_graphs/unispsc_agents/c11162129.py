# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162129 — Raw Material (segment 11).

Bespoke LangGraph agent logic for managing raw material state transitions,
including purity checks, moisture verification, and batch certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162129"
UNISPSC_TITLE = "Raw Material"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162129"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Raw Material
    purity_level: float
    moisture_content: float
    batch_id: str
    supplier_verified: bool
    refinement_required: bool


def inspect_material(state: State) -> dict[str, Any]:
    """Inspects the raw material for quality metrics."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.98)
    moisture = inp.get("moisture", 0.02)
    batch = inp.get("batch_id", "RM-UNISPSC-11162129-001")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_material"],
        "purity_level": purity,
        "moisture_content": moisture,
        "batch_id": batch,
        "supplier_verified": purity > 0.95,
        "refinement_required": moisture > 0.03
    }


def process_material(state: State) -> dict[str, Any]:
    """Determines if the material is ready or needs further refinement."""
    needs_refinement = state.get("refinement_required", False)
    status = "REFINING" if needs_refinement else "READY"

    return {
        "log": [f"{UNISPSC_CODE}:process_material:{status}"],
    }


def emit_certificate(state: State) -> dict[str, Any]:
    """Generates the final certificate for the raw material batch."""
    is_verified = state.get("supplier_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_id"),
            "purity": state.get("purity_level"),
            "quality_assured": is_verified,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_material)
_g.add_node("process", process_material)
_g.add_node("emit", emit_certificate)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
