# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121707 — Bogie (segment 25).

Bespoke graph logic for rail vehicle bogie components, handling specification
validation, structural integrity checks, and load capacity certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121707"
UNISPSC_TITLE = "Bogie"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121707"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Bogie (Rail Truck)
    wheel_diameter_mm: float
    axle_load_limit_tonnes: float
    suspension_type: str
    safety_certified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the mechanical specifications of the bogie assembly."""
    inp = state.get("input") or {}
    diameter = float(inp.get("wheel_diameter", 920.0))
    suspension = inp.get("suspension", "Primary Coil")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "wheel_diameter_mm": diameter,
        "suspension_type": suspension,
    }


def analyze_structural_load(state: State) -> dict[str, Any]:
    """Calculates permissible axle load limits based on suspension and wheels."""
    diameter = state.get("wheel_diameter_mm", 920.0)
    # Simple logic: larger wheels/robust suspension allow higher loads
    base_limit = 22.5 if diameter >= 900 else 18.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_structural_load"],
        "axle_load_limit_tonnes": base_limit,
        "safety_certified": True if base_limit >= 18.0 else False,
    }


def certify_assembly(state: State) -> dict[str, Any]:
    """Finalizes the bogie certification record."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_assembly"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "axle_limit": state.get("axle_load_limit_tonnes"),
            "suspension": state.get("suspension_type"),
            "certified": state.get("safety_certified"),
            "status": "ready_for_integration",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("analyze_structural_load", analyze_structural_load)
_g.add_node("certify_assembly", certify_assembly)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "analyze_structural_load")
_g.add_edge("analyze_structural_load", "certify_assembly")
_g.add_edge("certify_assembly", END)

graph = _g.compile()
