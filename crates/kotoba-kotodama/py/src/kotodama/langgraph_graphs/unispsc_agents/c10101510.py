# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10101510 — Livestock (segment 10).

Bespoke graph for livestock management, handling intake validation,
health inspection protocols, and quarantine verification for live animals.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10101510"
UNISPSC_TITLE = "Livestock"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10101510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    species: str
    health_status: str
    quarantine_verified: bool
    transport_lot_id: str


def validate_intake(state: State) -> dict[str, Any]:
    """Validates the species and transport documentation for the livestock lot."""
    inp = state.get("input") or {}
    species = inp.get("species", "bovine")
    lot_id = inp.get("lot_id", "UNASSIGNED")

    return {
        "log": [f"{UNISPSC_CODE}:validate_intake:species={species}:lot={lot_id}"],
        "species": species,
        "transport_lot_id": lot_id,
    }


def perform_health_inspection(state: State) -> dict[str, Any]:
    """Executes a simulated veterinary check based on the animal species."""
    species = state.get("species", "unknown")
    # In a real system, this might check specific markers per species
    status = "CLEAR" if species in ["bovine", "ovine", "porcine"] else "INCONCLUSIVE"

    return {
        "log": [f"{UNISPSC_CODE}:perform_health_inspection:status={status}"],
        "health_status": status,
    }


def verify_quarantine_status(state: State) -> dict[str, Any]:
    """Checks if the livestock has cleared the mandatory holding period."""
    lot_id = state.get("transport_lot_id")
    # Placeholder logic: verification passes if a valid lot_id is present
    verified = lot_id != "UNASSIGNED"

    return {
        "log": [f"{UNISPSC_CODE}:verify_quarantine_status:verified={verified}"],
        "quarantine_verified": verified,
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Produces the final livestock movement certificate."""
    health_ok = state.get("health_status") == "CLEAR"
    quarantine_ok = state.get("quarantine_verified", False)
    authorized = health_ok and quarantine_ok

    return {
        "log": [f"{UNISPSC_CODE}:emit_certification:authorized={authorized}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "species": state.get("species"),
            "lot_id": state.get("transport_lot_id"),
            "authorized": authorized,
            "status_code": "LV-ACK-001" if authorized else "LV-ERR-403",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_intake)
_g.add_node("inspect", perform_health_inspection)
_g.add_node("quarantine", verify_quarantine_status)
_g.add_node("emit", emit_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inspect")
_g.add_edge("inspect", "quarantine")
_g.add_edge("quarantine", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
