# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14122102 — Clay (segment 14).

Bespoke graph logic for processing raw clay material batches, including
inspection, refinement metrics, and dispatch preparation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14122102"
UNISPSC_TITLE = "Clay"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14122102"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Clay batches
    composition: list[str]
    moisture_content: float
    plasticity_index: float
    grading_class: str


def inspect_raw_material(state: State) -> dict[str, Any]:
    """Initial quality check for raw clay material incoming batch."""
    inp = state.get("input") or {}
    composition = inp.get("composition", ["kaolinite", "quartz"])
    moisture = float(inp.get("moisture", 18.5))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_material"],
        "composition": composition,
        "moisture_content": moisture,
    }


def refine_clay_batch(state: State) -> dict[str, Any]:
    """Analyze batch properties to determine plasticity and grading."""
    moisture = state.get("moisture_content", 0.0)
    # Heuristic calculation for clay plasticity index
    plasticity = 30.0 - (moisture * 0.7)

    if plasticity > 22:
        grading = "Fine Porcelain Grade"
    elif plasticity > 12:
        grading = "Standard Pottery Grade"
    else:
        grading = "Common Construction Grade"

    return {
        "log": [f"{UNISPSC_CODE}:refine_clay_batch"],
        "plasticity_index": round(plasticity, 2),
        "grading_class": grading,
    }


def prepare_dispatch(state: State) -> dict[str, Any]:
    """Finalize the batch for dispatch with calculated attributes."""
    return {
        "log": [f"{UNISPSC_CODE}:prepare_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "grading": state.get("grading_class"),
            "plasticity": state.get("plasticity_index"),
            "composition_verified": len(state.get("composition", [])) > 0,
            "status": "ready_for_delivery",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_raw_material)
_g.add_node("refine", refine_clay_batch)
_g.add_node("dispatch", prepare_dispatch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "refine")
_g.add_edge("refine", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
