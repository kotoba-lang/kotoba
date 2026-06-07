# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352103 — Catalyst (segment 12).
Specialized logic for chemical catalyst state management and reaction optimization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352103"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352103"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Catalysts
    reaction_stability: float
    substrate_type: str
    activation_energy_offset: float
    safety_compliance: bool
    is_exhausted: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Evaluates incoming substrate requirements and safety thresholds."""
    inp = state.get("input") or {}
    substrate = inp.get("substrate", "generic_chemical")
    required_purity = inp.get("min_purity", 0.95)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "substrate_type": substrate,
        "safety_compliance": required_purity > 0.90,
    }


def optimize_activation(state: State) -> dict[str, Any]:
    """Simulates the calculation of catalyst activation energy offsets."""
    # Deterministic logic based on substrate name length as a proxy for complexity
    complexity = len(state.get("substrate_type", ""))
    offset = 1.25 * complexity
    stability = 1.0 / (1.0 + (offset / 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:optimize_activation"],
        "activation_energy_offset": offset,
        "reaction_stability": stability,
        "is_exhausted": stability < 0.1,
    }


def certify_catalyst_batch(state: State) -> dict[str, Any]:
    """Finalizes the state and prepares the output record."""
    is_ok = state.get("safety_compliance", False) and not state.get("is_exhausted", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_catalyst_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_ok,
            "metrics": {
                "stability": state.get("reaction_stability"),
                "offset": state.get("activation_energy_offset")
            }
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specifications)
_g.add_node("optimize", optimize_activation)
_g.add_node("certify", certify_catalyst_batch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "optimize")
_g.add_edge("optimize", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
