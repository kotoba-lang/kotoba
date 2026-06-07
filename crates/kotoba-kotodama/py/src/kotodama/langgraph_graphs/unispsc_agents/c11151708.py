# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151708"
UNISPSC_TITLE = "Proc"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151708"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Processed Animal Fiber (Segment 11)
    lot_id: str
    fiber_purity: float
    moisture_content: float
    treatment_applied: str
    is_certified: bool


def inspect_raw_material(state: State) -> dict[str, Any]:
    """Inspects the incoming raw animal fiber for initial quality metrics."""
    inp = state.get("input") or {}
    lot = inp.get("batch_id", "BATCH-DEFAULT")
    purity = float(inp.get("purity", 0.85))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_material"],
        "lot_id": lot,
        "fiber_purity": purity,
        "is_certified": False,
    }


def refine_fiber(state: State) -> dict[str, Any]:
    """Applies scouring and drying treatments to stabilize the material."""
    purity = state.get("fiber_purity", 0.0)
    treatment = "Standard Scour" if purity > 0.9 else "Intensive Scour"
    return {
        "log": [f"{UNISPSC_CODE}:refine_fiber"],
        "treatment_applied": treatment,
        "moisture_content": 8.5,  # Target standardized moisture
    }


def validate_and_emit(state: State) -> dict[str, Any]:
    """Finalizes the processing record and emits the actor response."""
    moisture = state.get("moisture_content", 0.0)
    success = 5.0 <= moisture <= 12.0
    return {
        "log": [f"{UNISPSC_CODE}:validate_and_emit"],
        "is_certified": success,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "lot_id": state.get("lot_id"),
            "status": "PROCESSED" if success else "REJECTED",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_raw_material)
_g.add_node("refine", refine_fiber)
_g.add_node("emit", validate_and_emit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "refine")
_g.add_edge("refine", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
