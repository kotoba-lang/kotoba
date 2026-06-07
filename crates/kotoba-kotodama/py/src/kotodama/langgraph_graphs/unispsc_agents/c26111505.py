# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111505 — Chain (segment 26).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111505"
UNISPSC_TITLE = "Chain"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for power transmission and structural chains
    chain_material: str
    pitch_mm: float
    tensile_strength_kn: float
    inspection_passed: bool
    working_load_limit: float


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the physical specification of the chain components."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbon_steel")
    pitch = float(inp.get("pitch", 12.7))  # Default 1/2 inch
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "chain_material": material,
        "pitch_mm": pitch,
    }


def calculate_mechanical_limits(state: State) -> dict[str, Any]:
    """Calculates the mechanical limits based on material and geometry."""
    material = state.get("chain_material", "carbon_steel")
    # Heuristic strength calculation for industrial chain
    base_strength = 60.0 if material == "carbon_steel" else 45.0
    tensile = base_strength * (state.get("pitch_mm", 12.7) / 10.0)
    wll = tensile / 5.0  # Safety factor of 5
    return {
        "log": [f"{UNISPSC_CODE}:calculate_mechanical_limits"],
        "tensile_strength_kn": tensile,
        "working_load_limit": wll,
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Performs a virtual safety integrity check."""
    tensile = state.get("tensile_strength_kn", 0.0)
    passed = tensile > 25.0  # Minimum industrial requirement
    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity"],
        "inspection_passed": passed,
    }


def emit_result(state: State) -> dict[str, Any]:
    """Finalizes the chain technical data sheet."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "material": state.get("chain_material"),
                "pitch_mm": state.get("pitch_mm"),
                "tensile_kn": state.get("tensile_strength_kn"),
                "wll_kn": state.get("working_load_limit"),
                "certified": state.get("inspection_passed"),
            },
            "status": "COMPLIANT" if state.get("inspection_passed") else "NON_COMPLIANT",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("calc", calculate_mechanical_limits)
_g.add_node("verify", verify_integrity)
_g.add_node("emit", emit_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calc")
_g.add_edge("calc", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
