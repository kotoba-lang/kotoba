# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171505 — Wiper (segment 25).

Bespoke graph logic for validating and inspecting wiper blade specifications.
Ensures material compatibility and dimensional compliance for automotive wipers.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171505"
UNISPSC_TITLE = "Wiper"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for "Wiper"
    blade_type: str
    length_mm: int
    material_composition: str
    inspection_passed: bool
    fitment_validated: bool


def validate_fitment(state: State) -> dict[str, Any]:
    """Validates that the wiper dimensions are within acceptable ranges."""
    inp = state.get("input") or {}
    length = inp.get("length_mm", 0)
    # Standard automotive wipers are typically between 250mm and 800mm
    is_valid = 250 <= length <= 800

    return {
        "log": [f"{UNISPSC_CODE}:validate_fitment"],
        "length_mm": length,
        "fitment_validated": is_valid,
        "blade_type": inp.get("blade_type", "conventional"),
    }


def inspect_material(state: State) -> dict[str, Any]:
    """Simulates a quality inspection of the wiper blade material."""
    inp = state.get("input") or {}
    material = inp.get("material", "rubber")
    # Silicone and high-grade rubber pass inspection
    passed = material.lower() in ["silicone", "rubber", "synthetic"]

    return {
        "log": [f"{UNISPSC_CODE}:inspect_material"],
        "material_composition": material,
        "inspection_passed": passed,
    }


def certify_product(state: State) -> dict[str, Any]:
    """Finalizes the state and produces the result dictionary."""
    is_fit = state.get("fitment_validated", False)
    is_inspected = state.get("inspection_passed", False)
    ok = is_fit and is_inspected

    return {
        "log": [f"{UNISPSC_CODE}:certify_product"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": "APPROVED" if ok else "REJECTED",
            "metadata": {
                "blade_type": state.get("blade_type"),
                "length": state.get("length_mm"),
                "material": state.get("material_composition")
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_fitment", validate_fitment)
_g.add_node("inspect_material", inspect_material)
_g.add_node("certify_product", certify_product)

_g.add_edge(START, "validate_fitment")
_g.add_edge("validate_fitment", "inspect_material")
_g.add_edge("inspect_material", "certify_product")
_g.add_edge("certify_product", END)

graph = _g.compile()
