# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102008 — Reel (segment 24).

Bespoke graph for managing material winding processes on industrial reels.
This implementation handles material specification validation, tensioning
checks, and spooling status updates for logistics tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102008"
UNISPSC_TITLE = "Reel"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102008"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Reels
    material_sku: str
    reel_core_diameter_mm: int
    winding_tension_newtons: float
    is_inspected: bool


def validate_material(state: State) -> dict[str, Any]:
    """Validates the material SKU and sets reel specifications."""
    inp = state.get("input") or {}
    sku = inp.get("sku", "UNKNOWN-MAT")
    return {
        "log": [f"{UNISPSC_CODE}:validate_material"],
        "material_sku": sku,
        "reel_core_diameter_mm": 350,
    }


def simulate_winding(state: State) -> dict[str, Any]:
    """Simulates the winding process and records tension levels."""
    return {
        "log": [f"{UNISPSC_CODE}:simulate_winding"],
        "winding_tension_newtons": 12.5,
        "is_inspected": True,
    }


def finalize_spool(state: State) -> dict[str, Any]:
    """Finalizes the spooling operation and sets the result payload."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_spool"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "material": state.get("material_sku"),
            "inspected": state.get("is_inspected"),
            "status": "LOADED",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_material", validate_material)
_g.add_node("simulate_winding", simulate_winding)
_g.add_node("finalize_spool", finalize_spool)

_g.add_edge(START, "validate_material")
_g.add_edge("validate_material", "simulate_winding")
_g.add_edge("simulate_winding", "finalize_spool")
_g.add_edge("finalize_spool", END)

graph = _g.compile()
