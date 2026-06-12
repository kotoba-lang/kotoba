# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12131706"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12131706"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    reaction_id: str
    active_state: bool
    efficiency_score: float
    substrate_compatibility: str


def initialize_catalysis(state: State) -> dict[str, Any]:
    """Prepares the catalyst environment and identifies the batch."""
    inp = state.get("input") or {}
    rid = str(inp.get("batch_id", "CAT-DEFAULT-001"))
    return {
        "log": [f"{UNISPSC_CODE}:initialize_catalysis (batch: {rid})"],
        "reaction_id": rid,
        "active_state": False,
        "substrate_compatibility": inp.get("substrate", "standard-organic")
    }


def activate_reagents(state: State) -> dict[str, Any]:
    """Triggers the catalytic activation based on substrate affinity."""
    compatibility = state.get("substrate_compatibility", "standard-organic")
    # Simulate chemical affinity logic
    if compatibility == "high-affinity":
        efficiency = 0.98
    elif compatibility == "inhibited":
        efficiency = 0.45
    else:
        efficiency = 0.82

    return {
        "log": [f"{UNISPSC_CODE}:activate_reagents (efficiency_calculated: {efficiency})"],
        "active_state": True,
        "efficiency_score": efficiency
    }


def finalize_batch(state: State) -> dict[str, Any]:
    """Produces the final report for the catalytic process."""
    rid = state.get("reaction_id")
    eff = state.get("efficiency_score", 0.0)
    is_active = state.get("active_state", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "meta": {
                "batch_id": rid,
                "activation_confirmed": is_active,
                "yield_coefficient": eff
            },
            "status": "success" if eff > 0.5 else "low_yield"
        }
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_catalysis)
_g.add_node("activate", activate_reagents)
_g.add_node("finalize", finalize_batch)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "activate")
_g.add_edge("activate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
