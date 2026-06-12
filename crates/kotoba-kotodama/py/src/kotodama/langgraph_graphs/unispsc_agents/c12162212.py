# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12162212 — Catalyst (segment 12).

Bespoke graph logic for catalyst analysis, simulating reaction kinetics,
and certifying chemical purity standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12162212"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12162212"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific Catalyst fields
    substrate_compatibility: list[str]
    reaction_kinetics_delta: float
    purity_certification: bool
    thermal_threshold_celsius: int
    catalyst_phase: str


def evaluate_chemical_properties(state: State) -> dict[str, Any]:
    """Inspects the input for chemical specifications and phase requirements."""
    inp = state.get("input") or {}
    phase = inp.get("phase", "heterogeneous")
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_chemical_properties"],
        "catalyst_phase": phase,
        "thermal_threshold_celsius": inp.get("max_temp", 450),
        "substrate_compatibility": ["hydrocarbons", "aromatics"] if phase == "heterogeneous" else ["liquid_solvents"],
    }


def simulate_catalytic_cycle(state: State) -> dict[str, Any]:
    """Calculates the expected delta in activation energy."""
    # Mock simulation of reaction acceleration
    kinetics = 2.45 if state.get("catalyst_phase") == "heterogeneous" else 1.88
    return {
        "log": [f"{UNISPSC_CODE}:simulate_catalytic_cycle"],
        "reaction_kinetics_delta": kinetics,
        "purity_certification": True,
    }


def generate_safety_data_sheet(state: State) -> dict[str, Any]:
    """Produces the final actor result with domain metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_safety_data_sheet"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "phase": state.get("catalyst_phase"),
                "kinetics_score": state.get("reaction_kinetics_delta"),
                "temp_limit": state.get("thermal_threshold_celsius"),
                "compatible_substrates": state.get("substrate_compatibility"),
            },
            "status": "certified" if state.get("purity_certification") else "pending",
        },
    }


_g = StateGraph(State)

_g.add_node("evaluate", evaluate_chemical_properties)
_g.add_node("simulate", simulate_catalytic_cycle)
_g.add_node("certify", generate_safety_data_sheet)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "simulate")
_g.add_edge("simulate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
