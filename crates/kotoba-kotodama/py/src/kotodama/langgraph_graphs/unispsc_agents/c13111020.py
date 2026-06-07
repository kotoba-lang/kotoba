# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111020 — Metal (segment 13).

Bespoke graph logic for metal assaying, refinement, and certification protocols.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111020"
UNISPSC_TITLE = "Metal"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111020"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Metal domain-specific state fields
    metal_type: str
    assay_purity: float
    batch_tracking_id: str
    refinement_status: str
    is_certified: bool


def assay_ore(state: State) -> dict[str, Any]:
    """Analyzes the raw material composition and initializes tracking."""
    inp = state.get("input") or {}
    m_type = inp.get("metal_type", "Industrial Base Metal")
    initial_purity = inp.get("purity", 0.85)

    return {
        "log": [f"{UNISPSC_CODE}:assay_ore -> Identified {m_type} at {initial_purity*100}% purity"],
        "metal_type": m_type,
        "assay_purity": initial_purity,
        "batch_tracking_id": f"MET-{UNISPSC_CODE}-{id(state) % 10000:04d}",
    }


def refine_metal(state: State) -> dict[str, Any]:
    """Simulates the industrial refinement process to increase metal purity."""
    current_purity = state.get("assay_purity", 0.0)
    # Target high-grade purity (99.9%+)
    refined_purity = max(current_purity, 0.9992)

    return {
        "log": [f"{UNISPSC_CODE}:refine_metal -> Purity increased to {refined_purity*100}%"],
        "assay_purity": refined_purity,
        "refinement_status": "High-Grade Refined",
    }


def certify_and_manifest(state: State) -> dict[str, Any]:
    """Issues the final certificate of analysis and manifest for the metal batch."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_and_manifest"],
        "is_certified": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metal": state.get("metal_type"),
            "batch_id": state.get("batch_tracking_id"),
            "final_purity": state.get("assay_purity"),
            "grade": state.get("refinement_status"),
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("assay", assay_ore)
_g.add_node("refine", refine_metal)
_g.add_node("certify", certify_and_manifest)

_g.add_edge(START, "assay")
_g.add_edge("assay", "refine")
_g.add_edge("refine", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
