# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111512 — Vessel (segment 25).

Bespoke LangGraph implementation for vessel operations and seaworthiness
verification within the UNISPSC vehicle segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111512"
UNISPSC_TITLE = "Vessel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111512"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Vessel
    hull_integrity_verified: bool
    navigation_systems_online: bool
    propulsion_efficiency: float
    seaworthiness_rating: str
    vessel_class: str


def dockside_inspection(state: State) -> dict[str, Any]:
    """Perform initial physical hull and classification check."""
    inp = state.get("input") or {}
    v_class = inp.get("vessel_class", "Standard Commercial")

    return {
        "log": [f"{UNISPSC_CODE}:dockside_inspection: verifying hull and class {v_class}"],
        "hull_integrity_verified": True,
        "vessel_class": v_class,
    }


def bridge_diagnostics(state: State) -> dict[str, Any]:
    """Verify electronic systems and propulsion parameters."""
    return {
        "log": [f"{UNISPSC_CODE}:bridge_diagnostics: checking navigation and engines"],
        "navigation_systems_online": True,
        "propulsion_efficiency": 0.95,
    }


def certify_vessel(state: State) -> dict[str, Any]:
    """Finalize seaworthiness certification and emit result."""
    hull_ok = state.get("hull_integrity_verified", False)
    nav_ok = state.get("navigation_systems_online", False)

    rating = "A1" if hull_ok and nav_ok else "Pending"

    return {
        "log": [f"{UNISPSC_CODE}:certify_vessel: final rating {rating}"],
        "seaworthiness_rating": rating,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "seaworthiness_rating": rating,
            "status": "Ready for Dispatch" if rating == "A1" else "Flagged",
            "metadata": {
                "vessel_class": state.get("vessel_class"),
                "propulsion_efficiency": state.get("propulsion_efficiency"),
            }
        },
    }


_g = StateGraph(State)

_g.add_node("dockside_inspection", dockside_inspection)
_g.add_node("bridge_diagnostics", bridge_diagnostics)
_g.add_node("certify_vessel", certify_vessel)

_g.add_edge(START, "dockside_inspection")
_g.add_edge("dockside_inspection", "bridge_diagnostics")
_g.add_edge("bridge_diagnostics", "certify_vessel")
_g.add_edge("certify_vessel", END)

graph = _g.compile()
