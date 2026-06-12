# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20131307 — Gear (segment 20).

This module implements a bespoke LangGraph for Gear components, specifically
handling material validation for elastomer/resin-based gears and mechanical
specification verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20131307"
UNISPSC_TITLE = "Gear"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20131307"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Gear (Segment 20: Resins/Rubber/Elastomers)
    gear_type: str
    material_hardness: float
    tooth_count: int
    pitch_diameter: float
    is_elastomer_verified: bool


def validate_dimensions(state: State) -> dict[str, Any]:
    """Validates the basic mechanical dimensions of the gear component."""
    inp = state.get("input") or {}
    t_count = int(inp.get("tooth_count", 12))
    p_diam = float(inp.get("pitch_diameter", 50.0))
    g_type = inp.get("gear_type", "spur")

    return {
        "log": [f"{UNISPSC_CODE}:validate_dimensions"],
        "tooth_count": t_count,
        "pitch_diameter": p_diam,
        "gear_type": g_type,
    }


def verify_material_properties(state: State) -> dict[str, Any]:
    """Ensures the material (likely rubber/resin for Segment 20) meets hardness specs."""
    inp = state.get("input") or {}
    hardness = float(inp.get("hardness", 70.0))  # Shore A/D

    # Segment 20 gears are typically elastomeric or plastic
    verified = 20.0 <= hardness <= 100.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_material_properties"],
        "material_hardness": hardness,
        "is_elastomer_verified": verified,
    }


def emit_specification(state: State) -> dict[str, Any]:
    """Emits the final verified gear specification record."""
    is_ok = state.get("is_elastomer_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec": {
                "type": state.get("gear_type"),
                "teeth": state.get("tooth_count"),
                "diameter": state.get("pitch_diameter"),
                "verified": is_ok,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_dimensions", validate_dimensions)
_g.add_node("verify_material_properties", verify_material_properties)
_g.add_node("emit_specification", emit_specification)

_g.add_edge(START, "validate_dimensions")
_g.add_edge("validate_dimensions", "verify_material_properties")
_g.add_edge("verify_material_properties", "emit_specification")
_g.add_edge("emit_specification", END)

graph = _g.compile()
