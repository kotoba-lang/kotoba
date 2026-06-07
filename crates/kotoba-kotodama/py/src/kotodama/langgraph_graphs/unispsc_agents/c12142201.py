# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12142201 — Mag (segment 12).

This bespoke implementation handles state transitions for Mag items within
the Live Plant and Animal Material segment, focusing on intake validation,
domain-specific inspection, and metadata packaging.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12142201"
UNISPSC_TITLE = "Mag"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12142201"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for "Mag" (Live Material)
    inventory_id: str
    cultivar_type: str
    health_rating: int
    quarantine_cleared: bool


def ingest_sample(state: State) -> dict[str, Any]:
    """Receives and identifies the Mag sample material."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:ingest_sample"],
        "inventory_id": inp.get("id", "MAG-T-121"),
        "cultivar_type": inp.get("type", "Standard"),
    }


def evaluate_specimen(state: State) -> dict[str, Any]:
    """Evaluates the physical health and compliance of the specimen."""
    # Domain logic simulating health check for live material
    cultivar = state.get("cultivar_type", "Standard")
    health = 90 if cultivar == "Standard" else 98
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_specimen"],
        "health_rating": health,
        "quarantine_cleared": health > 80,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Finalizes the actor state and prepares the standardized result."""
    cleared = state.get("quarantine_cleared", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "record": {
                "id": state.get("inventory_id"),
                "rating": state.get("health_rating"),
                "cleared": cleared,
            },
            "ok": cleared,
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_sample)
_g.add_node("evaluate", evaluate_specimen)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
