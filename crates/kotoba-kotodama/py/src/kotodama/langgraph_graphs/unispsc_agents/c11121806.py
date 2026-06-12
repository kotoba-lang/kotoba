# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11121806 — Refining.
Bespoke implementation for vegetable/animal oil and fat refining processes.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11121806"
UNISPSC_TITLE = "Refining"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11121806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Refining (Segment 11)
    material_source: str
    target_purity: float
    actual_purity: float
    batch_volume_liters: float
    refinement_cycles: int


def initialize_refining(state: State) -> dict[str, Any]:
    """Analyze input material and set baseline refining parameters."""
    inp = state.get("input") or {}
    source = inp.get("source", "botanical_extract")
    volume = inp.get("volume", 500.0)

    return {
        "log": [f"{UNISPSC_CODE}:initialize"],
        "material_source": source,
        "batch_volume_liters": volume,
        "target_purity": 0.995,
        "actual_purity": 0.720,
        "refinement_cycles": 0,
    }


def perform_purification(state: State) -> dict[str, Any]:
    """Execute purification cycle to remove impurities and increase material purity."""
    current_purity = state.get("actual_purity", 0.0)
    cycles = state.get("refinement_cycles", 0)

    # Simulate a distillation/filtration cycle incrementing purity
    new_purity = min(0.998, current_purity + 0.15)

    return {
        "log": [f"{UNISPSC_CODE}:purification_cycle"],
        "actual_purity": new_purity,
        "refinement_cycles": cycles + 1,
    }


def verify_and_emit(state: State) -> dict[str, Any]:
    """Verify final purity against targets and emit the batch processing result."""
    purity = state.get("actual_purity", 0.0)
    target = state.get("target_purity", 0.995)
    source = state.get("material_source", "unknown")

    success = purity >= target

    return {
        "log": [f"{UNISPSC_CODE}:verify"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "final_purity": round(purity, 4),
            "source": source,
            "status": "APPROVED" if success else "PENDING_RE-REFINEMENT",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_refining)
_g.add_node("purify", perform_purification)
_g.add_node("verify", verify_and_emit)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "purify")
_g.add_edge("purify", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
