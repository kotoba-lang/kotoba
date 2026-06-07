# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12131507 — Chemical (segment 12).

Bespoke graph logic for handling chemical material state transitions,
safety data sheet verification, and purity analysis.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12131507"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12131507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical substances
    sds_verified: bool
    purity_level: float
    hazard_category: str
    storage_temp_range: str


def inspect_safety_data(state: State) -> dict[str, Any]:
    """Inspects the input for Safety Data Sheet (SDS) compliance."""
    inp = state.get("input") or {}
    has_sds = "sds_id" in inp or inp.get("safety_verified", False)
    hazard = inp.get("hazard_class", "non-hazardous")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_safety_data"],
        "sds_verified": has_sds,
        "hazard_category": hazard,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyzes the chemical composition and purity levels."""
    inp = state.get("input") or {}
    purity = float(inp.get("concentration", 0.99))
    storage = inp.get("storage_req", "room_temp")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "purity_level": purity,
        "storage_temp_range": storage,
    }


def finalize_chemical_lot(state: State) -> dict[str, Any]:
    """Finalizes the chemical lot record and emits the result."""
    is_safe = state.get("sds_verified", False)
    purity = state.get("purity_level", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_chemical_lot"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "certified" if is_safe and purity > 0.95 else "quarantine",
            "purity_verified": purity,
            "compliance": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_safety", inspect_safety_data)
_g.add_node("analyze_composition", analyze_composition)
_g.add_node("finalize_lot", finalize_chemical_lot)

_g.add_edge(START, "inspect_safety")
_g.add_edge("inspect_safety", "analyze_composition")
_g.add_edge("analyze_composition", "finalize_lot")
_g.add_edge("finalize_lot", END)

graph = _g.compile()
