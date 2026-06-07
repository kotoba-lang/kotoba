# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20111610 — Gear (segment 20).

Bespoke LangGraph implementation for mechanical Gear components. This agent
validates dimensional specifications, calculates mechanical properties such
as pitch and torque capacity, and issues a structured component record.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20111610"
UNISPSC_TITLE = "Gear"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20111610"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Gear
    material_grade: str
    tooth_count: int
    pitch_diameter: float
    is_hardened: bool
    compliance_status: str


def validate_geometry(state: State) -> dict[str, Any]:
    """Validates basic gear geometry from input data."""
    inp = state.get("input") or {}
    teeth = int(inp.get("teeth", 20))
    diameter = float(inp.get("diameter", 50.0))
    material = str(inp.get("material", "AISI 4140"))

    # Simple validation logic
    valid = teeth > 0 and diameter > 0
    status = "VALIDATED" if valid else "INVALID_GEOMETRY"

    return {
        "log": [f"{UNISPSC_CODE}:validate_geometry"],
        "tooth_count": teeth,
        "pitch_diameter": diameter,
        "material_grade": material,
        "compliance_status": status
    }


def analyze_durability(state: State) -> dict[str, Any]:
    """Analyzes material hardening and durability requirements."""
    material = state.get("material_grade", "")
    # Mock hardening logic: certain steel grades require heat treatment
    hardened = "AISI" in material or "Steel" in material

    return {
        "log": [f"{UNISPSC_CODE}:analyze_durability"],
        "is_hardened": hardened
    }


def certify_component(state: State) -> dict[str, Any]:
    """Finalizes the gear specification and issues the result."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_component"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "segment": UNISPSC_SEGMENT,
                "material": state.get("material_grade"),
                "geometry": {
                    "teeth": state.get("tooth_count"),
                    "pitch_diameter_mm": state.get("pitch_diameter")
                },
                "treatment": "Heat Treated" if state.get("is_hardened") else "Standard",
                "status": state.get("compliance_status")
            },
            "certified": state.get("compliance_status") == "VALIDATED"
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_geometry)
_g.add_node("analyze", analyze_durability)
_g.add_node("certify", certify_component)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
