# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101506 — Mineral (segment 11).

Bespoke graph for mineral assay and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101506"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    mineral_type: str
    chemical_composition: dict[str, float]
    purity_percentage: float
    certification_status: str


def inspect_mineral(state: State) -> dict[str, Any]:
    """Inspects the input specimen and identifies the mineral type."""
    inp = state.get("input") or {}
    mtype = inp.get("type", "Unknown Ore")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_mineral:{mtype}"],
        "mineral_type": mtype,
    }


def assay_composition(state: State) -> dict[str, Any]:
    """Simulates chemical analysis of the mineral composition."""
    # Simulation of assaying common minerals
    composition = {"Fe": 0.70, "O": 0.30} if "Iron" in state.get("mineral_type", "") else {"Si": 0.46, "O": 0.53}
    purity = 98.5
    return {
        "log": [f"{UNISPSC_CODE}:assay_composition:purity={purity}%"],
        "chemical_composition": composition,
        "purity_percentage": purity,
    }


def certify_mineral(state: State) -> dict[str, Any]:
    """Finalizes the certification based on purity and composition."""
    purity = state.get("purity_percentage", 0.0)
    status = "CERTIFIED" if purity > 95.0 else "UNREFINED"
    return {
        "log": [f"{UNISPSC_CODE}:certify_mineral:{status}"],
        "certification_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "mineral_type": state.get("mineral_type"),
            "purity": purity,
            "status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_mineral", inspect_mineral)
_g.add_node("assay_composition", assay_composition)
_g.add_node("certify_mineral", certify_mineral)

_g.add_edge(START, "inspect_mineral")
_g.add_edge("inspect_mineral", "assay_composition")
_g.add_edge("assay_composition", "certify_mineral")
_g.add_edge("certify_mineral", END)

graph = _g.compile()
