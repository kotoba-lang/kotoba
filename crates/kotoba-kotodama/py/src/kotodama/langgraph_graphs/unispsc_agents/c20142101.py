# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142101 — Pulley (segment 20).

This bespoke implementation handles mechanical advantage calculations,
load force assessment, and safety margin validation for pulley systems.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142101"
UNISPSC_TITLE = "Pulley"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Pulley
    mechanical_advantage: float
    input_force_required_n: float
    safety_margin: float
    is_load_safe: bool


def analyze_mechanics(state: State) -> dict[str, Any]:
    """Calculates theoretical mechanical advantage based on pulley configuration."""
    inp = state.get("input") or {}
    # Assume simple block and tackle where MA relates to rope segments supporting the load
    sheaves = inp.get("sheave_count", 1)
    friction_coefficient = inp.get("friction_coefficient", 0.05)

    # Simple model: MA is roughly 2*sheaves for a gun tackle / luff tackle setup
    theoretical_ma = sheaves * 2.0
    actual_ma = theoretical_ma * (1.0 - friction_coefficient)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_mechanics"],
        "mechanical_advantage": actual_ma,
    }


def calculate_load_dynamics(state: State) -> dict[str, Any]:
    """Determines the force required to move the specified load."""
    inp = state.get("input") or {}
    load_kg = inp.get("load_weight_kg", 50.0)
    ma = state.get("mechanical_advantage", 1.0)

    # Force (N) = (Mass * Gravity) / Mechanical Advantage
    gravity = 9.80665
    required_force = (load_kg * gravity) / ma

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_dynamics"],
        "input_force_required_n": required_force,
    }


def validate_safety_limits(state: State) -> dict[str, Any]:
    """Verifies that the required force does not exceed the rope/pulley rating."""
    inp = state.get("input") or {}
    max_rated_force_n = inp.get("max_rated_force_n", 1000.0)
    actual_force = state.get("input_force_required_n", 0.0)

    safety_margin = max_rated_force_n - actual_force
    is_safe = safety_margin > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_limits"],
        "safety_margin": safety_margin,
        "is_load_safe": is_safe,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "ok": is_safe,
            "analysis": {
                "mechanical_advantage": state.get("mechanical_advantage"),
                "required_force_n": actual_force,
                "safety_margin_n": safety_margin,
                "status": "PASS" if is_safe else "FAIL"
            },
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_mechanics)
_g.add_node("calculate", calculate_load_dynamics)
_g.add_node("validate", validate_safety_limits)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "calculate")
_g.add_edge("calculate", "validate")
_g.add_edge("validate", END)

graph = _g.compile()
