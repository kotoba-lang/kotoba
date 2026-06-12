# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101613 — Pulley.

This bespoke graph manages state transitions for Pulley procurement and
specification validation, including mechanical advantage calculations
and load capacity verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101613"
UNISPSC_TITLE = "Pulley"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101613"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Pulley
    mechanical_advantage: float
    load_capacity_kg: float
    sheave_count: int
    rope_diameter_mm: float
    is_compliant: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the physical requirements of the pulley system."""
    inp = state.get("input") or {}
    sheaves = int(inp.get("sheaves", 1))
    rope_dia = float(inp.get("rope_diameter", 10.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "sheave_count": sheaves,
        "rope_diameter_mm": rope_dia,
        "is_compliant": rope_dia > 0 and sheaves > 0
    }


def compute_mechanics(state: State) -> dict[str, Any]:
    """Calculates mechanical advantage and rated capacity."""
    sheaves = state.get("sheave_count", 1)
    # Simple model: Mechanical advantage is typically sheaves * 2 in a block and tackle
    ma = float(sheaves * 2)
    # Base capacity of 500kg per sheave for this actor's logic
    capacity = float(sheaves * 500.0)

    return {
        "log": [f"{UNISPSC_CODE}:compute_mechanics"],
        "mechanical_advantage": ma,
        "load_capacity_kg": capacity
    }


def finalize_asset_data(state: State) -> dict[str, Any]:
    """Formats the final response including domain metadata."""
    is_ok = state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "mechanical_advantage": state.get("mechanical_advantage"),
                "max_load_kg": state.get("load_capacity_kg"),
                "rope_limit_mm": state.get("rope_diameter_mm")
            },
            "verified": is_ok,
            "status": "active" if is_ok else "pending_review"
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("calculate", compute_mechanics)
_g.add_node("finalize", finalize_asset_data)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
