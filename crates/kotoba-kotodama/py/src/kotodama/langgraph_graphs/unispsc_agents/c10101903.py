# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10101903 — Live Animal (segment 10).

Bespoke graph logic for managing live animal lifecycle and transport.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10101903"
UNISPSC_TITLE = "Live Animal"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10101903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    animal_type: str
    health_status: str
    transport_lot_id: str
    quarantine_verified: bool


def validate_livestock(state: State) -> dict[str, Any]:
    """Validates the input for animal species and initial quarantine status."""
    inp = state.get("input") or {}
    species = inp.get("species", "undetermined")
    return {
        "log": [f"{UNISPSC_CODE}:validate_livestock:{species}"],
        "animal_type": species,
        "quarantine_verified": inp.get("quarantine", False),
    }


def check_health(state: State) -> dict[str, Any]:
    """Simulates a veterinary health check and assigns a transport lot."""
    animal = state.get("animal_type", "undetermined")
    lot_id = f"ANML-LOT-{UNISPSC_CODE}-{abs(hash(animal)) % 10000}"
    return {
        "log": [f"{UNISPSC_CODE}:check_health:certified"],
        "health_status": "cleared",
        "transport_lot_id": lot_id,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Finalizes the live animal shipment manifest and creates result object."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "manifest": {
                "species": state.get("animal_type"),
                "lot_id": state.get("transport_lot_id"),
                "health": state.get("health_status"),
                "quarantine": state.get("quarantine_verified"),
            },
            "success": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_livestock", validate_livestock)
_g.add_node("check_health", check_health)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "validate_livestock")
_g.add_edge("validate_livestock", "check_health")
_g.add_edge("check_health", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
