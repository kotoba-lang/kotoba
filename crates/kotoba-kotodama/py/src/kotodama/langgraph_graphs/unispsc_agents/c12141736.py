# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141736 — Silane (segment 12).

Bespoke graph logic for semiconductor-grade Silane (SiH4) state management.
Handles pyrophoric safety verification, purity analysis, and batch certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141736"
UNISPSC_TITLE = "Silane"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141736"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Silane gas handling
    pressure_psi: int
    purity_rating: float
    hazard_check: bool
    vessel_id: str


def check_safety(state: State) -> dict[str, Any]:
    """Validate containment pressure and pyrophoric hazard markers."""
    inp = state.get("input") or {}
    psi = inp.get("pressure_psi", 1800)
    # Silane is pyrophoric; verify pressure is within safe operating bounds
    safe = 500 < psi < 2500
    return {
        "log": [f"{UNISPSC_CODE}:check_safety"],
        "pressure_psi": psi,
        "hazard_check": safe,
    }


def analyze_gas(state: State) -> dict[str, Any]:
    """Perform simulated chromatography for semiconductor-grade purity."""
    return {
        "log": [f"{UNISPSC_CODE}:analyze_gas"],
        "purity_rating": 99.9999,
        "vessel_id": f"SIL-{UNISPSC_CODE}-B1",
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Generate the final compliance result for the Silane actor."""
    is_safe = state.get("hazard_check", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "APPROVED" if is_safe else "REJECTED",
            "purity": state.get("purity_rating"),
            "vessel": state.get("vessel_id"),
            "did": UNISPSC_DID,
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("safety", check_safety)
_g.add_node("analysis", analyze_gas)
_g.add_node("certification", certify_batch)

_g.add_edge(START, "safety")
_g.add_edge("safety", "analysis")
_g.add_edge("analysis", "certification")
_g.add_edge("certification", END)

graph = _g.compile()
