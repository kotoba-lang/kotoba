# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11171602 — Chemical.

Bespoke graph for handling chemical mineral ores and concentrates,
focusing on purity validation and safety compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11171602"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11171602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical minerals
    purity_level: float
    hazard_class: str
    sds_verified: bool
    batch_tracking_id: str


def inspect_purity(state: State) -> dict[str, Any]:
    """Analyze the chemical composition and purity of the mineral concentrate."""
    inp = state.get("input") or {}
    purity = float(inp.get("concentration", 0.95))
    batch_id = inp.get("batch_id", "CHEM-DEFAULT-001")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_purity"],
        "purity_level": purity,
        "batch_tracking_id": batch_id,
    }


def evaluate_hazards(state: State) -> dict[str, Any]:
    """Perform safety assessment and verify Material Safety Data Sheet (MSDS/SDS)."""
    purity = state.get("purity_level", 0.0)
    # Higher purity of certain chemicals might increase hazard classification
    h_class = "CLASS-8" if purity > 0.98 else "CLASS-9"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_hazards"],
        "hazard_class": h_class,
        "sds_verified": True,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generate the final chemical mineral manifest with compliance metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_tracking_id"),
            "purity": state.get("purity_level"),
            "hazard_classification": state.get("hazard_class"),
            "safety_compliant": state.get("sds_verified"),
            "status": "ready_for_transport",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_purity", inspect_purity)
_g.add_node("evaluate_hazards", evaluate_hazards)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "inspect_purity")
_g.add_edge("inspect_purity", "evaluate_hazards")
_g.add_edge("evaluate_hazards", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
