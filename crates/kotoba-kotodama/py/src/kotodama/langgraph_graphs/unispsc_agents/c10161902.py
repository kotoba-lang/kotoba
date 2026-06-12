# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10161902 — Seed (segment 10).
Bespoke implementation for seed lot processing and quality assurance.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161902"
UNISPSC_TITLE = "Seed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161902"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain state for Seed
    germination_percent: float
    batch_id: str
    purity_verified: bool
    certification_level: str


def validate_lot(state: State) -> dict[str, Any]:
    """Inspects the input seed lot for basic identification and purity."""
    inp = state.get("input") or {}
    batch = inp.get("lot_id", "SEED-999")
    purity = inp.get("purity", 0.99) > 0.98
    return {
        "log": [f"{UNISPSC_CODE}:validate_lot:{batch}"],
        "batch_id": batch,
        "purity_verified": purity,
    }


def analyze_viability(state: State) -> dict[str, Any]:
    """Calculates germination rate and assigns certification level."""
    inp = state.get("input") or {}
    rate = inp.get("germination", 0.92)
    level = "FOUNDATION" if rate > 0.95 else "CERTIFIED"
    return {
        "log": [f"{UNISPSC_CODE}:analyze_viability:{level}"],
        "germination_percent": rate,
        "certification_level": level,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Prepares the record for the seed inventory system."""
    batch = state.get("batch_id")
    level = state.get("certification_level")
    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch": batch,
            "certification": level,
            "verified": state.get("purity_verified", False),
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_lot", validate_lot)
_g.add_node("analyze_viability", analyze_viability)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "validate_lot")
_g.add_edge("validate_lot", "analyze_viability")
_g.add_edge("analyze_viability", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
