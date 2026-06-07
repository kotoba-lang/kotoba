# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20101700 — Excavation (segment 20).

Bespoke LangGraph implementation for excavation site assessment,
safety configuration, and operational planning.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101700"
UNISPSC_TITLE = "Excavation"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Excavation
    soil_classification: str
    target_depth_meters: float
    utility_clearance_verified: bool
    shoring_system_required: bool
    safety_protocol_certified: bool


def assess_site_conditions(state: State) -> dict[str, Any]:
    """Analyzes site input for soil type and depth requirements."""
    inp = state.get("input") or {}
    # Default to Type C (least stable) if not specified
    soil = inp.get("soil_type", "Type C (Granular/Loose)")
    depth = float(inp.get("target_depth", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:assess_site_conditions"],
        "soil_classification": soil,
        "target_depth_meters": depth,
        "utility_clearance_verified": inp.get("utility_check", False),
    }


def configure_safety_systems(state: State) -> dict[str, Any]:
    """Determines shoring and protective system requirements based on depth."""
    depth = state.get("target_depth_meters", 0.0)
    # OSHA standard: Excavations 5 feet (approx 1.52m) or deeper require protective systems
    needs_shoring = depth >= 1.52

    return {
        "log": [f"{UNISPSC_CODE}:configure_safety_systems"],
        "shoring_system_required": needs_shoring,
        "safety_protocol_certified": state.get("utility_clearance_verified", False),
    }


def finalize_excavation_plan(state: State) -> dict[str, Any]:
    """Finalizes the operational result for the excavation agent."""
    is_safe = state.get("safety_protocol_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_excavation_plan"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "plan_status": "CERTIFIED" if is_safe else "PENDING_UTILITY_CLEARANCE",
            "shoring_required": state.get("shoring_system_required"),
            "soil_type": state.get("soil_classification"),
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("assess_site_conditions", assess_site_conditions)
_g.add_node("configure_safety_systems", configure_safety_systems)
_g.add_node("finalize_excavation_plan", finalize_excavation_plan)

_g.add_edge(START, "assess_site_conditions")
_g.add_edge("assess_site_conditions", "configure_safety_systems")
_g.add_edge("configure_safety_systems", "finalize_excavation_plan")
_g.add_edge("finalize_excavation_plan", END)

graph = _g.compile()
