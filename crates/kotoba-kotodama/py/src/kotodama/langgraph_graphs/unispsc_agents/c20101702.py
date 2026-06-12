# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20101702 — Agent (segment 20).

This module defines a LangGraph agent for chemical or biological agents used in
mining and well drilling operations, providing property validation, dosage
optimization, and safety certification logic.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101702"
UNISPSC_TITLE = "Agent"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific state for Mining/Drilling Agent
    concentration_ratio: float
    viscosity_cp: float
    reaction_stability_index: float
    safety_compliance_verified: bool
    recommended_dosage_rate: float


def analyze_agent_properties(state: State) -> dict[str, Any]:
    """Analyzes the physical and chemical properties of the agent from input data."""
    inp = state.get("input") or {}
    conc = inp.get("concentration", 0.15)
    viscosity = inp.get("viscosity", 250.0)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_agent_properties"],
        "concentration_ratio": float(conc),
        "viscosity_cp": float(viscosity),
    }


def calculate_optimized_dosage(state: State) -> dict[str, Any]:
    """Calculates the optimal application rate based on concentration and viscosity."""
    conc = state.get("concentration_ratio", 0.0)
    visc = state.get("viscosity_cp", 0.0)

    # Heuristic calculation for drilling fluid additive dosage
    dosage = (conc * 50.0) + (visc / 1000.0)
    stability = 1.0 - (abs(0.5 - conc) * 0.2)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_optimized_dosage"],
        "recommended_dosage_rate": round(dosage, 4),
        "reaction_stability_index": round(stability, 4),
    }


def verify_safety_and_finalize(state: State) -> dict[str, Any]:
    """Performs final safety checks and emits the agent recommendation."""
    dosage = state.get("recommended_dosage_rate", 0.0)
    stability = state.get("reaction_stability_index", 0.0)

    # Safety requirements: stable reaction and dosage within operational bounds
    is_safe = stability > 0.85 and 0.0 < dosage < 100.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_and_finalize"],
        "safety_compliance_verified": is_safe,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "dosage_rate": dosage,
                "stability": stability,
                "compliance": "PASSED" if is_safe else "FAILED"
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_agent_properties)
_g.add_node("calculate", calculate_optimized_dosage)
_g.add_node("verify", verify_safety_and_finalize)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "calculate")
_g.add_edge("calculate", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
