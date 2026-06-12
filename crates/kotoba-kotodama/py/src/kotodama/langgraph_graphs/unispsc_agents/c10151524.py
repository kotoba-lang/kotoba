# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151524 — Protein (segment 10).

Bespoke logic for managing protein product specifications, characterization,
and quality certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151524"
UNISPSC_TITLE = "Protein"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151524"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    protein_source: str
    purity_percentage: float
    molecular_weight_daltons: int
    reconstitution_buffer: str
    is_safety_verified: bool


def validate_input(state: State) -> dict[str, Any]:
    """Validates the incoming protein specification and source metadata."""
    inp = state.get("input") or {}
    source = str(inp.get("source", "recombinant-human"))
    purity = float(inp.get("purity", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_input"],
        "protein_source": source,
        "purity_percentage": purity,
    }


def characterize_protein(state: State) -> dict[str, Any]:
    """Determines physical properties and safety status of the protein."""
    inp = state.get("input") or {}
    mw = int(inp.get("mw", 55000))
    buffer = str(inp.get("buffer", "TBS pH 8.0"))
    verified = state.get("purity_percentage", 0.0) > 98.0
    return {
        "log": [f"{UNISPSC_CODE}:characterize_protein"],
        "molecular_weight_daltons": mw,
        "reconstitution_buffer": buffer,
        "is_safety_verified": verified,
    }


def final_certification(state: State) -> dict[str, Any]:
    """Emits final results with certification and handling instructions."""
    verified = state.get("is_safety_verified", False)
    purity = state.get("purity_percentage", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:final_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "certified" if verified else "pending",
            "purity": purity,
            "handling": "Store at -20C",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_input)
_g.add_node("characterize", characterize_protein)
_g.add_node("certify", final_certification)
_g.add_edge(START, "validate")
_g.add_edge("validate", "characterize")
_g.add_edge("characterize", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
