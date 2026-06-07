# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172200 — Interior systems (segment 25).

Bespoke LangGraph logic for managing vehicle interior systems specifications,
safety assessments, and component inventory tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172200"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172200"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Interior Systems
    component_inventory: list[str]
    safety_compliance: bool
    ergonomic_index: float
    material_verification: str


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the input requirements for the vehicle interior system."""
    inp = state.get("input") or {}
    inventory = inp.get("inventory", ["seating", "dashboard", "door_panels"])
    material = inp.get("material_type", "synthetic_leather")

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "component_inventory": inventory,
        "material_verification": material,
    }


def analyze_interior_specs(state: State) -> dict[str, Any]:
    """Analyzes specifications to determine safety compliance and ergonomics."""
    inventory = state.get("component_inventory", [])
    material = state.get("material_verification", "unknown")

    # Safety logic: requires core components (e.g., seating and dashboard)
    has_critical = "seating" in inventory and "dashboard" in inventory
    compliance = has_critical and material != "unknown"

    # Ergonomics heuristic based on presence of key comfort components
    e_index = 0.92 if "seating" in inventory and "door_panels" in inventory else 0.45

    return {
        "log": [f"{UNISPSC_CODE}:analyze_interior_specs"],
        "safety_compliance": compliance,
        "ergonomic_index": e_index,
    }


def synthesize_result(state: State) -> dict[str, Any]:
    """Synthesizes the analysis into a final result dictionary for the actor."""
    return {
        "log": [f"{UNISPSC_CODE}:synthesize_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "compliance": state.get("safety_compliance"),
                "ergonomics": state.get("ergonomic_index"),
                "material": state.get("material_verification"),
            },
            "components_processed": len(state.get("component_inventory", [])),
            "status": "verified",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("analyze", analyze_interior_specs)
_g.add_node("synthesize", synthesize_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "synthesize")
_g.add_edge("synthesize", END)

graph = _g.compile()
