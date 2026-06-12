# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172003 — Shock Absorber (segment 25).

This bespoke LangGraph agent manages the validation and performance testing
lifecycle for automotive shock absorbers, ensuring hydraulic integrity and
damping curve compliance before dispatching certification metadata.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172003"
UNISPSC_TITLE = "Shock Absorber"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172003"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain state for Shock Absorber
    hydraulic_pressure_psi: int
    seal_integrity_verified: bool
    damping_coefficient: float
    safety_rating: str


def inspect_seals(state: State) -> dict[str, Any]:
    """Performs a simulated pressure test to verify hydraulic seal integrity."""
    inp = state.get("input") or {}
    test_pressure = inp.get("test_pressure_psi", 160)

    # Requirement: seal must hold at least 150 PSI
    is_valid = test_pressure >= 150

    return {
        "log": [f"{UNISPSC_CODE}:inspect_seals"],
        "hydraulic_pressure_psi": test_pressure,
        "seal_integrity_verified": is_valid,
    }


def analyze_damping(state: State) -> dict[str, Any]:
    """Analyzes the damping coefficient based on compression and rebound data."""
    is_sealed = state.get("seal_integrity_verified", False)

    # Simulate damping calculation; compromised seals lead to failure
    coefficient = 0.85 if is_sealed else 0.20

    return {
        "log": [f"{UNISPSC_CODE}:analyze_damping"],
        "damping_coefficient": coefficient,
        "safety_rating": "A" if coefficient > 0.8 else "F",
    }


def certify_component(state: State) -> dict[str, Any]:
    """Issues the final actor result including UNISPSC and DID metadata."""
    rating = state.get("safety_rating", "F")
    passed = rating == "A"

    return {
        "log": [f"{UNISPSC_CODE}:certify_component"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": passed,
            "telemetry": {
                "pressure": state.get("hydraulic_pressure_psi"),
                "damping": state.get("damping_coefficient"),
                "rating": rating
            },
            "status": "APPROVED" if passed else "REJECTED_QUALITY_CONTROL"
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_seals", inspect_seals)
_g.add_node("analyze_damping", analyze_damping)
_g.add_node("certify_component", certify_component)

_g.add_edge(START, "inspect_seals")
_g.add_edge("inspect_seals", "analyze_damping")
_g.add_edge("analyze_damping", "certify_component")
_g.add_edge("certify_component", END)

graph = _g.compile()
