# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10122101 — Live Animal (segment 10).
Bespoke logic for live animal procurement, health assessment, and quarantine verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10122101"
UNISPSC_TITLE = "Live Animal"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10122101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Live Animal
    species_id: str
    health_status: str
    quarantine_verified: bool
    transport_lot_id: str
    welfare_cert_issued: bool


def validate_livestock(state: State) -> dict[str, Any]:
    """Inspects input for animal species and initial health declaration."""
    inp = state.get("input") or {}
    species = inp.get("species", "bovine")
    health = inp.get("health_status", "fair")

    return {
        "log": [f"{UNISPSC_CODE}:validate_livestock:checking_{species}"],
        "species_id": species,
        "health_status": health,
    }


def verify_quarantine(state: State) -> dict[str, Any]:
    """Verifies if the animal meets the required quarantine protocols."""
    health = state.get("health_status", "unknown")
    # Simulate a check: only animals in 'good' or 'fair' health pass quarantine
    is_safe = health.lower() in ["good", "fair", "healthy"]

    return {
        "log": [f"{UNISPSC_CODE}:verify_quarantine:result_{is_safe}"],
        "quarantine_verified": is_safe,
        "transport_lot_id": "ANIM-LOT-2026-05" if is_safe else "REJECTED",
    }


def finalize_clearance(state: State) -> dict[str, Any]:
    """Issues final clearance for transport if all checks pass."""
    is_verified = state.get("quarantine_verified", False)
    species = state.get("species_id", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_clearance"],
        "welfare_cert_issued": is_verified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "species": species,
            "quarantine_passed": is_verified,
            "lot_number": state.get("transport_lot_id"),
            "ok": is_verified,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_livestock", validate_livestock)
_g.add_node("verify_quarantine", verify_quarantine)
_g.add_node("finalize_clearance", finalize_clearance)

_g.add_edge(START, "validate_livestock")
_g.add_edge("validate_livestock", "verify_quarantine")
_g.add_edge("verify_quarantine", "finalize_clearance")
_g.add_edge("finalize_clearance", END)

graph = _g.compile()
