# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101630 — Crane (segment 24).

Bespoke graph for crane operations management, handling load validation,
safety envelope verification, and material movement sequencing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101630"
UNISPSC_TITLE = "Crane"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101630"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Crane domain fields
    load_weight_kg: float
    boom_extension_m: float
    safety_margin: float
    outriggers_deployed: bool
    path_clearance_verified: bool


def configure_lift(state: State) -> dict[str, Any]:
    """Initializes lift parameters from input payload."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))
    extension = float(inp.get("extension", 10.0))

    return {
        "log": [f"{UNISPSC_CODE}:configure_lift -> weight={weight}kg, ext={extension}m"],
        "load_weight_kg": weight,
        "boom_extension_m": extension,
        "outriggers_deployed": True,
    }


def verify_safety_envelope(state: State) -> dict[str, Any]:
    """Calculates stability and verifies if the lift is within the safety chart."""
    weight = state.get("load_weight_kg", 0.0)
    extension = state.get("boom_extension_m", 1.0)

    # Simple physics proxy: capacity decreases as extension increases
    max_capacity = 50000.0 / (extension / 5.0)
    margin = (max_capacity - weight) / max_capacity if max_capacity > 0 else -1.0
    is_safe = margin > 0.15 and state.get("outriggers_deployed", False)

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_envelope -> margin={margin:.2f}, safe={is_safe}"],
        "safety_margin": margin,
        "path_clearance_verified": is_safe,
    }


def execute_movement(state: State) -> dict[str, Any]:
    """Finalizes the operation and emits the result if safety checks passed."""
    is_safe = state.get("path_clearance_verified", False)

    status = "SUCCESS" if is_safe else "ABORTED_SAFETY_VIOLATION"
    return {
        "log": [f"{UNISPSC_CODE}:execute_movement -> status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "operation_status": status,
            "safety_margin": state.get("safety_margin", 0.0),
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("configure_lift", configure_lift)
_g.add_node("verify_safety_envelope", verify_safety_envelope)
_g.add_node("execute_movement", execute_movement)

_g.add_edge(START, "configure_lift")
_g.add_edge("configure_lift", "verify_safety_envelope")
_g.add_edge("verify_safety_envelope", "execute_movement")
_g.add_edge("execute_movement", END)

graph = _g.compile()
