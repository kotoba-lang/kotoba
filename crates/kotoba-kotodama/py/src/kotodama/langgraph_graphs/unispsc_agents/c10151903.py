# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151903 — Seed (segment 10).

Bespoke LangGraph implementation for seed quality verification, certification checks,
and inventory finalization for agricultural and botanical seeds.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151903"
UNISPSC_TITLE = "Seed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Seed
    germination_rate: float
    purity_percentage: float
    lot_number: str
    is_certified: bool
    treatment_type: str


def inspect_quality(state: State) -> dict[str, Any]:
    """Inspects the seed batch for germination rate and purity levels."""
    inp = state.get("input") or {}
    g_rate = inp.get("germination_rate", 0.95)
    purity = inp.get("purity_percentage", 0.99)
    lot = inp.get("lot_number", "BATCH-2026-05-23")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_quality - lot {lot} analyzed"],
        "germination_rate": g_rate,
        "purity_percentage": purity,
        "lot_number": lot,
    }


def verify_certification(state: State) -> dict[str, Any]:
    """Verifies if the seed batch meets regulatory standards for segment 10."""
    g_rate = state.get("germination_rate", 0.0)
    purity = state.get("purity_percentage", 0.0)
    treatment = (state.get("input") or {}).get("treatment_type", "Untreated")

    # Standards require >= 85% germination and >= 98% purity
    certified = g_rate >= 0.85 and purity >= 0.98

    return {
        "log": [f"{UNISPSC_CODE}:verify_certification - compliance status: {certified}"],
        "is_certified": certified,
        "treatment_type": treatment,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Updates the inventory record with certification status and lot metadata."""
    certified = state.get("is_certified", False)
    lot = state.get("lot_number", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory - record sealed"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "lot_number": lot,
            "is_certified": certified,
            "treatment": state.get("treatment_type"),
            "status": "APPROVED" if certified else "QUARANTINE",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_quality", inspect_quality)
_g.add_node("verify_certification", verify_certification)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "inspect_quality")
_g.add_edge("inspect_quality", "verify_certification")
_g.add_edge("verify_certification", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
