# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101719 — Catalyst (segment 11).

Bespoke logic for catalytic material analysis and specification. This agent
models the lifecycle of a catalyst specification within the minerals and
precious metals segment, evaluating material purity and thermal stability.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101719"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101719"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Catalyst (Segment 11)
    material_composition: str
    purity_pct: float
    thermal_limit_k: int
    is_active: bool


def inspect_composition(state: State) -> dict[str, Any]:
    """Analyzes the input material for known catalytic components."""
    inp = state.get("input") or {}
    composition = inp.get("material", "Unknown Noble Metal")
    purity = inp.get("purity", 99.9)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition"],
        "material_composition": composition,
        "purity_pct": purity,
        "is_active": purity > 95.0,
    }


def evaluate_thermal_stability(state: State) -> dict[str, Any]:
    """Calculates the theoretical thermal stability based on composition."""
    composition = state.get("material_composition", "")

    # Simple heuristic for thermal limits in Kelvin
    limit = 1200
    if "Platinum" in composition:
        limit = 2000
    elif "Palladium" in composition:
        limit = 1800
    elif "Zeolite" in composition:
        limit = 1000

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_thermal_stability"],
        "thermal_limit_k": limit,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Generates the final catalyst specification and metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec": {
                "material": state.get("material_composition"),
                "purity": f"{state.get('purity_pct')}%",
                "operating_temp_limit": f"{state.get('thermal_limit_k')}K",
                "status": "Validated" if state.get("is_active") else "Degraded",
            },
            "ok": state.get("is_active", False),
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_composition", inspect_composition)
_g.add_node("evaluate_thermal_stability", evaluate_thermal_stability)
_g.add_node("finalize_specification", finalize_specification)

_g.add_edge(START, "inspect_composition")
_g.add_edge("inspect_composition", "evaluate_thermal_stability")
_g.add_edge("evaluate_thermal_stability", "finalize_specification")
_g.add_edge("finalize_specification", END)

graph = _g.compile()
