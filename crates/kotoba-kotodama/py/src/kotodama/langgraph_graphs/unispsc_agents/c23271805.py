# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271805 — Iron Powder (segment 23).

Bespoke logic for Iron Powder metallurgical processing and batch validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271805"
UNISPSC_TITLE = "Iron Powder"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271805"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Iron Powder metallurgical state
    purity_percent: float
    mesh_size: int
    iron_type: str
    batch_certified: bool


def inspect_specification(state: State) -> dict[str, Any]:
    """Inspects the input specs for iron powder purity and particle size."""
    inp = state.get("input") or {}
    # Default to standard industrial grade if not provided
    purity = inp.get("purity", 98.5)
    mesh = inp.get("mesh", 100)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specification purity={purity} mesh={mesh}"],
        "purity_percent": purity,
        "mesh_size": mesh
    }


def assess_grade(state: State) -> dict[str, Any]:
    """Determines the metallurgical grade based on purity and mesh size."""
    purity = state.get("purity_percent", 0.0)

    # Categorize iron type based on purity thresholds
    if purity >= 99.7:
        grade = "electrolytic"
    elif purity >= 99.0:
        grade = "atomized"
    else:
        grade = "reduced_sponge"

    return {
        "log": [f"{UNISPSC_CODE}:assess_grade determined_grade={grade}"],
        "iron_type": grade,
        "batch_certified": purity >= 98.0
    }


def finalize_batch(state: State) -> dict[str, Any]:
    """Finalizes the processing and emits the batch result metadata."""
    certified = state.get("batch_certified", False)
    iron_type = state.get("iron_type", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_batch certified={certified}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metallurgy": {
                "type": iron_type,
                "purity": state.get("purity_percent"),
                "mesh": state.get("mesh_size")
            },
            "certified": certified,
            "status": "cleared_for_metallurgy" if certified else "quality_rejection"
        }
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specification)
_g.add_node("assess", assess_grade)
_g.add_node("finalize", finalize_batch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
