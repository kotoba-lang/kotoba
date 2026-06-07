# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10121803 — Livestock (segment 10).

Bespoke LangGraph logic for managing livestock assets, providing workflows
for species identification, health inspection, and inventory registration.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10121803"
UNISPSC_TITLE = "Livestock"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10121803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    animal_species: str
    health_status: str
    transport_lot_id: str
    quarantine_verified: bool


def intake_livestock(state: State) -> dict[str, Any]:
    """Parse input to identify the livestock lot and species."""
    inp = state.get("input") or {}
    species = inp.get("species", "bovine")
    lot_id = inp.get("lot_id", "LIV-UNK-001")

    return {
        "log": [f"{UNISPSC_CODE}:intake_livestock(species={species}, lot={lot_id})"],
        "animal_species": species,
        "transport_lot_id": lot_id,
    }


def verify_health_compliance(state: State) -> dict[str, Any]:
    """Check health certifications and determine quarantine status."""
    inp = state.get("input") or {}
    # Domain logic: expect 'health_cert' to be true for immediate clearance
    has_cert = inp.get("health_cert", False)
    status = "certified" if has_cert else "pending_inspection"

    return {
        "log": [f"{UNISPSC_CODE}:verify_health_compliance(status={status})"],
        "health_status": status,
        "quarantine_verified": has_cert,
    }


def record_inventory_state(state: State) -> dict[str, Any]:
    """Finalize the livestock record for the asset management system."""
    is_ok = state.get("quarantine_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:record_inventory_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "species": state.get("animal_species"),
            "lot_id": state.get("transport_lot_id"),
            "health": state.get("health_status"),
            "status": "ready" if is_ok else "hold",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("intake", intake_livestock)
_g.add_node("verify", verify_health_compliance)
_g.add_node("record", record_inventory_state)

_g.add_edge(START, "intake")
_g.add_edge("intake", "verify")
_g.add_edge("verify", "record")
_g.add_edge("record", END)

graph = _g.compile()
