# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20131201 — Belt (segment 20).
Bespoke implementation for industrial conveyor belt specification and mining compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20131201"
UNISPSC_TITLE = "Belt"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20131201"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for industrial belt specification
    belt_material: str
    width_mm: float
    tension_capacity_kn: float
    is_fire_resistant: bool
    safety_score: float


def configure_belt(state: State) -> dict[str, Any]:
    """Initializes belt configuration from input parameters."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "Reinforced Synthetic"))
    width = float(inp.get("width", 1000.0))
    return {
        "log": [f"{UNISPSC_CODE}:configure_belt"],
        "belt_material": material,
        "width_mm": width,
    }


def calculate_tension(state: State) -> dict[str, Any]:
    """Calculates operational tension capacity based on material and width."""
    width = state.get("width_mm", 0.0)
    material = state.get("belt_material", "")

    # Heuristic tension calculation for mining-grade belts
    base = 50.0 if "Steel" in material else 20.0
    capacity = (width / 100.0) * base

    return {
        "log": [f"{UNISPSC_CODE}:calculate_tension"],
        "tension_capacity_kn": capacity,
        "is_fire_resistant": "Fire" in material or "FR" in material or "Flame" in material,
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Evaluates the final safety score and produces the certification result."""
    capacity = state.get("tension_capacity_kn", 0.0)
    fr = state.get("is_fire_resistant", False)

    # Safety score calculation (0-100)
    score = (capacity / 500.0) * 80.0
    if fr:
        score += 20.0

    final_score = min(score, 100.0)
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "safety_score": final_score,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "assessment": "COMPLIANT" if final_score >= 40.0 else "NON-COMPLIANT",
            "metrics": {
                "capacity_kn": capacity,
                "fire_rated": fr,
                "score": final_score,
            },
        },
    }


_g = StateGraph(State)
_g.add_node("configure_belt", configure_belt)
_g.add_node("calculate_tension", calculate_tension)
_g.add_node("verify_safety", verify_safety)

_g.add_edge(START, "configure_belt")
_g.add_edge("configure_belt", "calculate_tension")
_g.add_edge("calculate_tension", "verify_safety")
_g.add_edge("verify_safety", END)

graph = _g.compile()
