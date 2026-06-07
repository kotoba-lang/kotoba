# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141757 — Material (segment 12).

This bespoke implementation handles the state transitions for animal reproductive
material assets, including viability assessment and cryogenic storage logging.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141757"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141757"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Animal Reproductive Material
    batch_id: str
    viability_score: float
    quarantine_verified: bool
    storage_temp_celsius: float


def inspect_batch(state: State) -> dict[str, Any]:
    """Validates the provenance and batch metadata of the reproductive material."""
    inp = state.get("input") or {}
    batch = inp.get("batch_id", "ST-000")
    # Simulate a quarantine check based on presence of a certificate
    is_cleared = "origin_cert" in inp

    return {
        "log": [f"{UNISPSC_CODE}:inspect_batch"],
        "batch_id": batch,
        "quarantine_verified": is_cleared,
    }


def evaluate_viability(state: State) -> dict[str, Any]:
    """Calculates biological viability metrics for the material sample."""
    # A simplified simulation: cleared batches get a standard viability score
    score = 0.92 if state.get("quarantine_verified") else 0.40

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_viability"],
        "viability_score": score,
        "storage_temp_celsius": -196.1,  # Liquid nitrogen temperature
    }


def register_asset(state: State) -> dict[str, Any]:
    """Finalizes the asset registration in the local inventory ledger."""
    viable = state.get("viability_score", 0) > 0.75

    return {
        "log": [f"{UNISPSC_CODE}:register_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "asset_id": state.get("batch_id"),
            "viability": state.get("viability_score"),
            "temp": state.get("storage_temp_celsius"),
            "ok": viable,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_batch)
_g.add_node("evaluate", evaluate_viability)
_g.add_node("register", register_asset)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "evaluate")
_g.add_edge("evaluate", "register")
_g.add_edge("register", END)

graph = _g.compile()
