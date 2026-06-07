# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10101602 — Commodity (segment 10).

This bespoke graph manages the lifecycle of a Live Animal commodity lot,
handling identification, health screening, and transport readiness.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10101602"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10101602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Live Animal commodities
    lot_id: str
    species_verified: bool
    health_index: float
    quarantine_status: str


def validate_lot(state: State) -> dict[str, Any]:
    """Validates the incoming lot identification and species data."""
    inp = state.get("input") or {}
    lot_id = inp.get("lot_id", "COMM-LOT-001")
    species = inp.get("species", "Generic")

    return {
        "log": [f"{UNISPSC_CODE}:validate_lot id={lot_id}"],
        "lot_id": lot_id,
        "species_verified": species != "Unknown",
    }


def perform_health_check(state: State) -> dict[str, Any]:
    """Simulates a health audit of the live animal commodity."""
    # Mock logic: higher health index for verified species
    h_index = 0.98 if state.get("species_verified") else 0.45
    status = "CLEAR" if h_index > 0.8 else "RE-INSPECT"

    return {
        "log": [f"{UNISPSC_CODE}:perform_health_check status={status}"],
        "health_index": h_index,
        "quarantine_status": status,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Finalizes the commodity record and emits the result."""
    lot = state.get("lot_id")
    status = state.get("quarantine_status")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "lot_id": lot,
            "disposition": "READY_FOR_SHIPMENT" if status == "CLEAR" else "QUARANTINE_HOLD",
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_lot", validate_lot)
_g.add_node("perform_health_check", perform_health_check)
_g.add_node("finalize_record", finalize_record)

_g.add_edge(START, "validate_lot")
_g.add_edge("validate_lot", "perform_health_check")
_g.add_edge("perform_health_check", "finalize_record")
_g.add_edge("finalize_record", END)

graph = _g.compile()
