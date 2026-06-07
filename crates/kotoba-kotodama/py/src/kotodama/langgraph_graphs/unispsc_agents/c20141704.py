# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141704 — Gear Spec (segment 20).

This module provides bespoke logic for technical specification of gears
used in well drilling and completion machinery.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141704"
UNISPSC_TITLE = "Gear Spec"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Gear Spec
    gear_diameter_in: float
    tensile_strength_psi: int
    alloy_composition: str
    tolerance_check_passed: bool


def validate_input(state: State) -> dict[str, Any]:
    """Ingest and validate the initial gear specification request."""
    inp = state.get("input") or {}
    diameter = float(inp.get("diameter", 12.0))
    # Default tensile strength based on segment 20 drilling standards
    strength = int(inp.get("tensile", 85000))
    return {
        "log": [f"{UNISPSC_CODE}:validate_input"],
        "gear_diameter_in": diameter,
        "tensile_strength_psi": strength,
    }


def process_metallurgy(state: State) -> dict[str, Any]:
    """Determines material composition and checks tolerances for the gear."""
    strength = state.get("tensile_strength_psi", 0)
    diameter = state.get("gear_diameter_in", 0.0)

    # Metallurgy selection logic for wellhead gear environments
    if strength > 100000:
        alloy = "AISI 4340 Nickel-Chromium-Molybdenum Steel"
    else:
        alloy = "AISI 4140 Chromium-Molybdenum Steel"

    # Basic geometric sanity check
    passed = diameter > 0.1 and strength > 40000

    return {
        "log": [f"{UNISPSC_CODE}:process_metallurgy"],
        "alloy_composition": alloy,
        "tolerance_check_passed": passed,
    }


def emit_specifications(state: State) -> dict[str, Any]:
    """Produces the final verified gear specification metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_specifications"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "specs": {
                "material": state.get("alloy_composition"),
                "diameter_inches": state.get("gear_diameter_in"),
                "tensile_psi": state.get("tensile_strength_psi"),
            },
            "validation": {
                "status": "passed" if state.get("tolerance_check_passed") else "failed",
                "segment": UNISPSC_SEGMENT,
                "actor_did": UNISPSC_DID,
                "verified": True
            },
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_input)
_g.add_node("metallurgy", process_metallurgy)
_g.add_node("emit", emit_specifications)

_g.add_edge(START, "validate")
_g.add_edge("validate", "metallurgy")
_g.add_edge("metallurgy", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
