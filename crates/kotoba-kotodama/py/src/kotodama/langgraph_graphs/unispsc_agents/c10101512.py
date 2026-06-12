# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10101512 — Livestock.

Bespoke graph logic for managing live animal intake, health screening,
and quarantine verification for livestock management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10101512"
UNISPSC_TITLE = "Livestock"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10101512"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Livestock domain fields
    health_status: str
    transport_lot_id: str
    quarantine_verified: bool
    species_classification: str


def validate_intake(state: State) -> dict[str, Any]:
    """Validates incoming livestock transport documentation and lot IDs."""
    inp = state.get("input") or {}
    lot_id = inp.get("lot_id", "LSTK-TEMP-000")
    species = inp.get("species", "Bovine")

    return {
        "log": [f"{UNISPSC_CODE}:validate_intake lot={lot_id} species={species}"],
        "transport_lot_id": lot_id,
        "species_classification": species,
        "quarantine_verified": False,
    }


def health_assessment(state: State) -> dict[str, Any]:
    """Simulates a health check and quarantine verification process."""
    lot_id = state.get("transport_lot_id")
    # Logic simulation: lots with valid prefixes pass screening
    is_cleared = lot_id != "LSTK-TEMP-000"

    return {
        "log": [f"{UNISPSC_CODE}:health_assessment cleared={is_cleared}"],
        "health_status": "OPTIMAL" if is_cleared else "PENDING_REVIEW",
        "quarantine_verified": is_cleared,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Finalizes the livestock asset record and generates the agent output."""
    verified = state.get("quarantine_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "lot_id": state.get("transport_lot_id"),
            "species": state.get("species_classification"),
            "health_report": state.get("health_status"),
            "status": "ACTIVE" if verified else "QUARANTINED",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_intake", validate_intake)
_g.add_node("health_assessment", health_assessment)
_g.add_node("finalize_record", finalize_record)

_g.add_edge(START, "validate_intake")
_g.add_edge("validate_intake", "health_assessment")
_g.add_edge("health_assessment", "finalize_record")
_g.add_edge("finalize_record", END)

graph = _g.compile()
