# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26112103 — Brake (segment 26).

Bespoke LangGraph implementation for brake system component analysis,
hydraulic pressure validation, and safety certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26112103"
UNISPSC_TITLE = "Brake"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26112103"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Brake analysis
    wear_index: float
    hydraulic_pressure_psi: int
    pad_material: str
    safety_certified: bool


def inspect_wear(state: State) -> dict[str, Any]:
    """Evaluates the wear level of the brake friction surfaces."""
    inp = state.get("input") or {}
    # Default values simulate a standard inspection if no input is provided
    wear = float(inp.get("wear_index", 0.15))
    material = str(inp.get("pad_material", "Ceramic"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_wear"],
        "wear_index": wear,
        "pad_material": material,
    }


def validate_hydraulics(state: State) -> dict[str, Any]:
    """Tests the hydraulic integrity of the braking system."""
    inp = state.get("input") or {}
    pressure = int(inp.get("pressure", 1200))

    return {
        "log": [f"{UNISPSC_CODE}:validate_hydraulics"],
        "hydraulic_pressure_psi": pressure,
    }


def certify_safety(state: State) -> dict[str, Any]:
    """Finalizes the safety audit and issues the component result."""
    wear = state.get("wear_index", 0.0)
    pressure = state.get("hydraulic_pressure_psi", 0)

    # Logic: Wear must be below 0.8 and pressure above 800 PSI for certification
    is_safe = wear < 0.8 and pressure > 800

    return {
        "log": [f"{UNISPSC_CODE}:certify_safety"],
        "safety_certified": is_safe,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "audit_data": {
                "wear_compliant": wear < 0.8,
                "pressure_compliant": pressure > 800,
                "material_detected": state.get("pad_material", "Unknown"),
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_wear", inspect_wear)
_g.add_node("validate_hydraulics", validate_hydraulics)
_g.add_node("certify_safety", certify_safety)

_g.add_edge(START, "inspect_wear")
_g.add_edge("inspect_wear", "validate_hydraulics")
_g.add_edge("validate_hydraulics", "certify_safety")
_g.add_edge("certify_safety", END)

graph = _g.compile()
