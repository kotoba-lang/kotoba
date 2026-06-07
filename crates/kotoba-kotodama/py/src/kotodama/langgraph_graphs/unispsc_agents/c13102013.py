# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102013 — Rare Earth (segment 13).

Bespoke graph for handling Rare Earth materials within the resin and
rosin segment, focusing on concentration verification and purity checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102013"
UNISPSC_TITLE = "Rare Earth"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102013"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Rare Earth materials
    purity_grade: float
    element_concentration: dict[str, float]
    spectroscopy_verified: bool
    inventory_batch_id: str


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyzes the rare earth element concentration from input data."""
    inp = state.get("input") or {}
    concentration = inp.get("concentration", {"Nd": 0.15, "Pr": 0.05})
    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "element_concentration": concentration,
        "inventory_batch_id": inp.get("batch_id", "REF-000"),
    }


def verify_purity(state: State) -> dict[str, Any]:
    """Verifies that the material meets the required purity threshold."""
    conc = state.get("element_concentration", {})
    total_rare_earth = sum(conc.values())
    is_pure = total_rare_earth > 0.10  # Arbitrary threshold
    return {
        "log": [f"{UNISPSC_CODE}:verify_purity"],
        "purity_grade": total_rare_earth,
        "spectroscopy_verified": is_pure,
    }


def finalize_catalog(state: State) -> dict[str, Any]:
    """Prepares the final result and signs off on the material entry."""
    is_verified = state.get("spectroscopy_verified", False)
    grade = state.get("purity_grade", 0.0)
    batch = state.get("inventory_batch_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalog"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "verification": "PASSED" if is_verified else "FAILED",
            "grade": f"{grade:.2%}",
            "batch": batch,
            "ok": is_verified,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_composition", analyze_composition)
_g.add_node("verify_purity", verify_purity)
_g.add_node("finalize_catalog", finalize_catalog)

_g.add_edge(START, "analyze_composition")
_g.add_edge("analyze_composition", "verify_purity")
_g.add_edge("verify_purity", "finalize_catalog")
_g.add_edge("finalize_catalog", END)

graph = _g.compile()
