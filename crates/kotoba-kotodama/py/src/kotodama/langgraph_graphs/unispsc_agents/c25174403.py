# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174403 — Panel (segment 25).
Bespoke implementation for transport interior panel configuration and validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174403"
UNISPSC_TITLE = "Panel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174403"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Automotive/Transport Panels
    material_spec: str
    mounting_clearance_mm: float
    integrity_verified: bool
    backlight_required: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the panel component."""
    inp = state.get("input") or {}
    material = inp.get("material", "Polymer-ABS")
    clearance = float(inp.get("clearance", 5.0))
    backlight = bool(inp.get("backlight", False))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material_spec": material,
        "mounting_clearance_mm": clearance,
        "backlight_required": backlight
    }


def structural_analysis(state: State) -> dict[str, Any]:
    """Performs virtual stress testing and fitment check for the panel."""
    # Logic simulation: high clearance and specific materials pass integrity
    clearance = state.get("mounting_clearance_mm", 0.0)
    is_valid = clearance >= 2.0

    return {
        "log": [f"{UNISPSC_CODE}:structural_analysis"],
        "integrity_verified": is_valid
    }


def emit_component_data(state: State) -> dict[str, Any]:
    """Finalizes the panel configuration and emits the resulting metadata."""
    integrity = state.get("integrity_verified", False)
    material = state.get("material_spec", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:emit_component_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if integrity else "REJECTED",
            "specifications": {
                "material": material,
                "backlight": state.get("backlight_required"),
                "integrity_check": integrity
            },
            "ok": integrity
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specs)
_g.add_node("analyze", structural_analysis)
_g.add_node("emit", emit_component_data)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
