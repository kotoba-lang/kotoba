# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11171501 — Ore (segment 11).

Bespoke logic for mineral inspection, refinement, and lot documentation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11171501"
UNISPSC_TITLE = "Ore"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11171501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    mineral_composition: dict[str, float]
    purity_index: float
    hazard_detected: bool
    refining_method: str
    tracking_number: str


def inspect_ore(state: State) -> dict[str, Any]:
    """Analyzes raw ore input for chemical composition and safety."""
    inp = state.get("input") or {}
    comp = inp.get("composition", {"Fe": 0.62, "O": 0.30, "Si": 0.08})
    hazard = inp.get("has_toxic_byproducts", False)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_ore"],
        "mineral_composition": comp,
        "purity_index": comp.get("Fe", 0.0) if isinstance(comp, dict) else 0.0,
        "hazard_detected": hazard,
        "tracking_number": inp.get("lot_id", "GEN-ORE-000")
    }


def refine_ore(state: State) -> dict[str, Any]:
    """Determines the appropriate refining method based on purity."""
    purity = state.get("purity_index", 0.0)
    method = "Smelting" if purity > 0.5 else "Leaching"

    return {
        "log": [f"{UNISPSC_CODE}:refine_ore"],
        "refining_method": method
    }


def certify_lot(state: State) -> dict[str, Any]:
    """Finalizes the lot certificate and result payload."""
    hazard = state.get("hazard_detected", False)
    method = state.get("refining_method", "None")
    tracking = state.get("tracking_number", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:certify_lot"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": not hazard,
            "method": method,
            "lot_id": tracking,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_ore)
_g.add_node("refine", refine_ore)
_g.add_node("certify", certify_lot)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "refine")
_g.add_edge("refine", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
