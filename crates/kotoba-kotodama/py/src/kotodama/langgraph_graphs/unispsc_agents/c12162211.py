# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12162211 — Chem (segment 12).

Bespoke graph logic for chemical substance management and purity verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12162211"
UNISPSC_TITLE = "Chem"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12162211"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Chem
    safety_protocol_verified: bool
    molecular_weight: float
    hazardous_rating: int
    purity_coefficient: float


def inspect_safety(state: State) -> dict[str, Any]:
    """Inspects the chemical input for safety protocols and base properties."""
    inp = state.get("input") or {}
    hazard = int(inp.get("hazardous_rating", 0))
    mw = float(inp.get("molecular_weight", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_safety: mw={mw}, hazard={hazard}"],
        "molecular_weight": mw,
        "hazardous_rating": hazard,
        "safety_protocol_verified": hazard < 5,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Simulates analysis of chemical composition and purity."""
    inp = state.get("input") or {}
    coeff = float(inp.get("purity", 0.95))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition: purity_coeff={coeff}"],
        "purity_coefficient": coeff,
    }


def emit_certificate(state: State) -> dict[str, Any]:
    """Emits the final chemical analysis certificate and result state."""
    is_safe = state.get("safety_protocol_verified", False)
    coeff = state.get("purity_coefficient", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:emit_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purity": coeff,
            "certified_safe": is_safe,
            "status": "APPROVED" if (is_safe and coeff > 0.8) else "REJECTED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_safety)
_g.add_node("analyze", analyze_composition)
_g.add_node("emit", emit_certificate)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
