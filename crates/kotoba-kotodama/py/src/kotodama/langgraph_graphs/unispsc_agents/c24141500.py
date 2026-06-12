# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141500 — Securing (segment 24).
Bespoke implementation for cargo load securing and stability management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141500"
UNISPSC_TITLE = "Securing"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for cargo securing
    securing_method: str
    tension_force_newtons: float
    anchor_points_verified: int
    safety_clasp_active: bool
    stability_rating: float


def evaluate_load_requirements(state: State) -> dict[str, Any]:
    """Analyze input to determine required securing hardware and force."""
    inp = state.get("input") or {}
    weight = inp.get("weight_kg", 500)
    method = "steel_chains" if weight > 2000 else "polyester_webbing"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_load_requirements"],
        "securing_method": method,
        "anchor_points_verified": 4 if weight < 1000 else 8,
    }


def apply_securing_tension(state: State) -> dict[str, Any]:
    """Simulate the physical application of tensioning devices."""
    method = state.get("securing_method", "webbing")
    force = 2500.0 if method == "steel_chains" else 1200.0

    return {
        "log": [f"{UNISPSC_CODE}:apply_securing_tension"],
        "tension_force_newtons": force,
        "safety_clasp_active": True,
    }


def validate_transport_readiness(state: State) -> dict[str, Any]:
    """Perform final stability check and emit result."""
    tension = state.get("tension_force_newtons", 0.0)
    anchors = state.get("anchor_points_verified", 0)
    clasp = state.get("safety_clasp_active", False)

    # Simple heuristic for stability
    ready = clasp and anchors >= 4 and tension > 1000
    stability = 0.98 if ready else 0.45

    return {
        "log": [f"{UNISPSC_CODE}:validate_transport_readiness"],
        "stability_rating": stability,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "LOAD_SECURED" if ready else "INSUFFICIENT_RESTRAINT",
            "stability_index": stability,
            "ok": ready,
        },
    }


_g = StateGraph(State)

_g.add_node("evaluate", evaluate_load_requirements)
_g.add_node("tension", apply_securing_tension)
_g.add_node("validate", validate_transport_readiness)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "tension")
_g.add_edge("tension", "validate")
_g.add_edge("validate", END)

graph = _g.compile()
