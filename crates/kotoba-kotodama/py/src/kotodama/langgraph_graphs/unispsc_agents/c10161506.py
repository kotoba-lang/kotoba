# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10161506 — Livestock (segment 10).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161506"
UNISPSC_TITLE = "Livestock"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Livestock
    species: str
    health_rating: int
    quarantine_verified: bool
    lot_identifier: str


def intake_livestock(state: State) -> dict[str, Any]:
    """Records the arrival of livestock and identifies the species."""
    inp = state.get("input") or {}
    species = inp.get("species", "unspecified")
    lot_id = inp.get("lot_id", "L-DEFAULT")
    return {
        "log": [f"{UNISPSC_CODE}:intake species={species}"],
        "species": species,
        "lot_identifier": lot_id,
    }


def perform_health_check(state: State) -> dict[str, Any]:
    """Evaluates the health status of the livestock batch."""
    inp = state.get("input") or {}
    rating = inp.get("health_rating", 100)
    # Threshold for automatic clearance
    verified = rating >= 80
    return {
        "log": [f"{UNISPSC_CODE}:health_check rating={rating}"],
        "health_rating": rating,
        "quarantine_verified": verified,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Compiles the final status for the livestock ledger."""
    verified = state.get("quarantine_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize verified={verified}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "lot_id": state.get("lot_identifier"),
            "status": "APPROVED" if verified else "HOLD_FOR_QUARANTINE",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("intake", intake_livestock)
_g.add_node("check", perform_health_check)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "intake")
_g.add_edge("intake", "check")
_g.add_edge("check", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
