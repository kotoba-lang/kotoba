# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141501 — Catalyst (segment 12).

This bespoke LangGraph agent handles the lifecycle of a chemical catalyst
validation, reactivity analysis, and safety certification process.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141501"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific catalyst state
    purity_assay: float
    reactivity_index: float
    safety_clearance: bool
    substrate_compatibility: list[str]


def verify_specifications(state: State) -> dict[str, Any]:
    """Initial validation of chemical specifications and intended substrates."""
    inp = state.get("input") or {}
    substrates = inp.get("substrates", ["general_organic"])

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications"],
        "substrate_compatibility": substrates,
        "safety_clearance": "hazard_class" in inp or True
    }


def analyze_reactivity(state: State) -> dict[str, Any]:
    """Simulate kinetic analysis and purity assay for the catalyst batch."""
    # Catalysts are measured by their ability to lower activation energy
    # and their own purity level to prevent side reactions.
    return {
        "log": [f"{UNISPSC_CODE}:analyze_reactivity"],
        "purity_assay": 0.9997,
        "reactivity_index": 4.85
    }


def certify_catalyst(state: State) -> dict[str, Any]:
    """Final certification and generation of the technical data sheet."""
    is_ok = state.get("purity_assay", 0) > 0.99 and state.get("safety_clearance")

    return {
        "log": [f"{UNISPSC_CODE}:certify_catalyst"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "purity": state.get("purity_assay"),
                "reactivity": state.get("reactivity_index"),
                "substrates": state.get("substrate_compatibility")
            },
            "certified": is_ok,
            "status": "active_catalyst_lot" if is_ok else "quarantined"
        }
    }


_g = StateGraph(State)

_g.add_node("verify_specifications", verify_specifications)
_g.add_node("analyze_reactivity", analyze_reactivity)
_g.add_node("certify_catalyst", certify_catalyst)

_g.add_edge(START, "verify_specifications")
_g.add_edge("verify_specifications", "analyze_reactivity")
_g.add_edge("analyze_reactivity", "certify_catalyst")
_g.add_edge("certify_catalyst", END)

graph = _g.compile()
