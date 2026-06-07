# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101703 — Rock Bin (segment 24).
Specialized logic for managing industrial rock storage, fill levels, and bin integrity.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101703"
UNISPSC_TITLE = "Rock Bin"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    fill_level_percent: float
    bin_capacity_tons: int
    structural_integrity_score: float
    material_type: str


def inspect_bin(state: State) -> dict[str, Any]:
    """Check sensor data and structural integrity for the rock bin."""
    inp = state.get("input") or {}
    capacity = inp.get("capacity", 500)
    # Simulate an initial inspection or state recovery
    return {
        "log": [f"{UNISPSC_CODE}:inspect_bin"],
        "bin_capacity_tons": capacity,
        "structural_integrity_score": inp.get("integrity_sensor", 0.98),
        "fill_level_percent": state.get("fill_level_percent", 0.0),
    }


def update_loading_state(state: State) -> dict[str, Any]:
    """Process incoming material weight and update bin fill level."""
    inp = state.get("input") or {}
    added_weight = inp.get("load_weight_tons", 0)
    capacity = state.get("bin_capacity_tons", 500)

    current_fill = state.get("fill_level_percent", 0.0)
    new_fill_percent = current_fill + (added_weight / capacity * 100.0)

    # Cap at 100% or overflow logic
    if new_fill_percent > 100.0:
        new_fill_percent = 100.0

    return {
        "log": [f"{UNISPSC_CODE}:update_loading_state"],
        "fill_level_percent": round(new_fill_percent, 2),
        "material_type": inp.get("material", "Crushed Basalt"),
    }


def emit_storage_report(state: State) -> dict[str, Any]:
    """Generate final telemetry and state confirmation for the Rock Bin."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_storage_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "fill_level": f"{state.get('fill_level_percent')}%",
                "material": state.get("material_type"),
                "status": "Optimal" if state.get("structural_integrity_score", 0) > 0.8 else "Maintenance Required",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_bin", inspect_bin)
_g.add_node("update_loading_state", update_loading_state)
_g.add_node("emit_storage_report", emit_storage_report)

_g.add_edge(START, "inspect_bin")
_g.add_edge("inspect_bin", "update_loading_state")
_g.add_edge("update_loading_state", "emit_storage_report")
_g.add_edge("emit_storage_report", END)

graph = _g.compile()
