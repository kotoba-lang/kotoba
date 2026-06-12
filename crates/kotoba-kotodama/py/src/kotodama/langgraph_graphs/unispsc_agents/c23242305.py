# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242305 — Rotary drill bits (segment 23).

Bespoke graph for managing rotary drill bit specifications, material compatibility,
and availability checks within the manufacturing machinery segment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242305"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242305"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Rotary Drill Bits
    bit_diameter_mm: float
    shank_style: str
    material_grade: str
    in_stock: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validate requested drill bit dimensions and mounting interface."""
    inp = state.get("input") or {}
    # Extract dimensions with defaults
    diameter = float(inp.get("diameter", 0.0))
    shank = str(inp.get("shank", "Straight"))
    grade = str(inp.get("grade", "High-Speed Steel"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "bit_diameter_mm": diameter,
        "shank_style": shank,
        "material_grade": grade,
    }


def inventory_lookup(state: State) -> dict[str, Any]:
    """Simulate a lookup in the manufacturing tooling database for availability."""
    diameter = state.get("bit_diameter_mm", 0.0)
    # standard stock: bits between 0.5mm and 25.0mm are common
    available = 0.5 <= diameter <= 25.0

    return {
        "log": [f"{UNISPSC_CODE}:inventory_lookup"],
        "in_stock": available,
    }


def compile_fulfillment_data(state: State) -> dict[str, Any]:
    """Prepare the final response including availability and spec summary."""
    is_available = state.get("in_stock", False)

    return {
        "log": [f"{UNISPSC_CODE}:compile_fulfillment_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "fulfillment_status": "immediate" if is_available else "custom_order",
            "specification": {
                "diameter": state.get("bit_diameter_mm"),
                "shank": state.get("shank_style"),
                "material": state.get("material_grade"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specifications", validate_specifications)
_g.add_node("inventory_lookup", inventory_lookup)
_g.add_node("compile_fulfillment_data", compile_fulfillment_data)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "inventory_lookup")
_g.add_edge("inventory_lookup", "compile_fulfillment_data")
_g.add_edge("compile_fulfillment_data", END)

graph = _g.compile()
