# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141914 — Catalyst (segment 12).

Bespoke logic for managing catalyst properties, reaction optimization, and
batch certification within the chemical production domain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141914"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141914"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Catalyst
    reaction_type: str
    purity_level: float
    active_agent: str
    substrate_compatibility: list[str]
    is_certified: bool


def initialize_catalyst(state: State) -> dict[str, Any]:
    """Sets up the initial state for the catalytic agent based on input parameters."""
    inp = state.get("input") or {}
    reaction_type = inp.get("reaction_type", "heterogeneous")
    active_agent = inp.get("active_agent", "Palladium-on-Carbon")

    return {
        "log": [f"{UNISPSC_CODE}:initialize_catalyst"],
        "reaction_type": reaction_type,
        "active_agent": active_agent,
        "purity_level": 0.9995,
        "is_certified": False
    }


def optimize_reaction_path(state: State) -> dict[str, Any]:
    """Simulates optimization of catalyst performance for specific substrates."""
    reaction_type = state.get("reaction_type")

    # Determine substrate compatibility based on catalyst architecture
    if reaction_type == "homogeneous":
        subs = ["liquid_phase_organics", "chiral_solvents"]
    else:
        subs = ["gas_phase_hydrocarbons", "olefin_streams"]

    return {
        "log": [f"{UNISPSC_CODE}:optimize_reaction_path"],
        "substrate_compatibility": subs
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Finalizes the catalyst record and emits the performance certificate."""
    is_ready = state.get("purity_level", 0) > 0.99

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "is_certified": is_ready,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "catalyst_status": "active" if is_ready else "quarantined",
            "composition": state.get("active_agent"),
            "compatibility": state.get("substrate_compatibility"),
            "certified_purity": state.get("purity_level")
        }
    }


_g = StateGraph(State)
_g.add_node("initialize_catalyst", initialize_catalyst)
_g.add_node("optimize_reaction_path", optimize_reaction_path)
_g.add_node("certify_batch", certify_batch)

_g.add_edge(START, "initialize_catalyst")
_g.add_edge("initialize_catalyst", "optimize_reaction_path")
_g.add_edge("optimize_reaction_path", "certify_batch")
_g.add_edge("certify_batch", END)

graph = _g.compile()
