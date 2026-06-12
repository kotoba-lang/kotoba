# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10161510 — Seed (segment 10).

This bespoke implementation handles state transitions for seed lot inspection,
purity verification, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161510"
UNISPSC_TITLE = "Seed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Seed
    seed_variety: str
    germination_rate: float
    purity_percent: float
    treatment_applied: bool
    batch_id: str


def inspect_lot(state: State) -> dict[str, Any]:
    """Inspects the seed lot for variety and batch identification."""
    inp = state.get("input") or {}
    variety = inp.get("variety", "Standard")
    batch = inp.get("batch", "LOT-999")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_lot:{batch}"],
        "seed_variety": variety,
        "batch_id": batch,
    }


def verify_purity(state: State) -> dict[str, Any]:
    """Simulates a purity and germination test on the seed sample."""
    # Logic simulating lab results
    purity = 98.5
    germination = 92.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_purity:{purity}%"],
        "purity_percent": purity,
        "germination_rate": germination,
    }


def certify_seed(state: State) -> dict[str, Any]:
    """Finalizes certification based on quality metrics."""
    is_certified = state.get("purity_percent", 0) > 95 and state.get("germination_rate", 0) > 85

    return {
        "log": [f"{UNISPSC_CODE}:certify_seed:status={is_certified}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "batch": state.get("batch_id"),
            "certified": is_certified,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_lot", inspect_lot)
_g.add_node("verify_purity", verify_purity)
_g.add_node("certify_seed", certify_seed)

_g.add_edge(START, "inspect_lot")
_g.add_edge("inspect_lot", "verify_purity")
_g.add_edge("verify_purity", "certify_seed")
_g.add_edge("certify_seed", END)

graph = _g.compile()
