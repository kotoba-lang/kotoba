# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102208 — Inflator (segment 24).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102208"
UNISPSC_TITLE = "Inflator"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102208"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    target_psi: float
    current_psi: float
    valve_connected: bool
    safety_bypass: bool


def initialize_inflator(state: State) -> dict[str, Any]:
    """Prepares the inflator device and validates target pressure."""
    inp = state.get("input") or {}
    target = float(inp.get("target_psi", 32.0))
    return {
        "log": [f"{UNISPSC_CODE}:initialize_inflator"],
        "target_psi": target,
        "current_psi": 0.0,
        "valve_connected": True,
        "safety_bypass": False,
    }


def pressurize(state: State) -> dict[str, Any]:
    """Increments the internal pressure to match the target setpoint."""
    target = state.get("target_psi", 0.0)
    # Simulate step-wise inflation logic
    return {
        "log": [f"{UNISPSC_CODE}:pressurize"],
        "current_psi": target,
    }


def verify_and_emit(state: State) -> dict[str, Any]:
    """Verifies final pressure stability and generates the output result."""
    current = state.get("current_psi", 0.0)
    target = state.get("target_psi", 0.0)
    success = abs(current - target) < 0.1

    return {
        "log": [f"{UNISPSC_CODE}:verify_and_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "final_psi": current,
            "stabilized": success,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_inflator)
_g.add_node("pressurize", pressurize)
_g.add_node("emit", verify_and_emit)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "pressurize")
_g.add_edge("pressurize", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
