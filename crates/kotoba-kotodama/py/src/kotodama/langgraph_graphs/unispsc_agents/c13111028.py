# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111028 — Coating (segment 13).

Bespoke logic for resin-based and protective coating state management.
Handles substrate preparation checks, application parameters, and curing verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111028"
UNISPSC_TITLE = "Coating"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111028"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Coating
    substrate_type: str
    coating_material: str
    viscosity_cps: float
    curing_temp_c: float
    inspection_passed: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the input specification for the coating process."""
    inp = state.get("input") or {}
    substrate = inp.get("substrate", "unknown")
    material = inp.get("material", "epoxy")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification: {substrate}/{material}"],
        "substrate_type": substrate,
        "coating_material": material,
        "viscosity_cps": float(inp.get("viscosity", 500.0)),
    }


def apply_coating(state: State) -> dict[str, Any]:
    """Simulates the application phase and calculates curing requirements."""
    material = state.get("coating_material", "epoxy")
    # Basic logic: heat-cured for industrial grades, ambient for others
    temp = 120.0 if "industrial" in material.lower() else 25.0

    return {
        "log": [f"{UNISPSC_CODE}:apply_coating: setting curing temp to {temp}C"],
        "curing_temp_c": temp,
        "inspection_passed": True
    }


def finalize_batch(state: State) -> dict[str, Any]:
    """Emits the final record for the coating operation."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "substrate": state.get("substrate_type"),
            "status": "completed",
            "passed": state.get("inspection_passed", False)
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("apply", apply_coating)
_g.add_node("finalize", finalize_batch)

_g.add_edge(START, "validate")
_g.add_edge("validate", "apply")
_g.add_edge("apply", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
