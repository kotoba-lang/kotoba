# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151535 — Commodity.
Bespoke graph logic for tracking commodity-grade live material state transitions.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151535"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151535"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Commodity (Segment 10 context)
    health_status: str
    transport_lot_id: str
    quarantine_verified: bool
    origin_facility: str


def intake_validation(state: State) -> dict[str, Any]:
    """Validates the incoming lot and assigns a transport identifier."""
    inp = state.get("input") or {}
    lot_id = inp.get("lot_id", "LOT-GENERIC-10151535")
    facility = inp.get("facility", "FAC-DEFAULT")

    return {
        "log": [f"{UNISPSC_CODE}:intake_validation -> {lot_id}"],
        "transport_lot_id": lot_id,
        "origin_facility": facility,
    }


def health_clearance(state: State) -> dict[str, Any]:
    """Performs health inspection and quarantine verification."""
    inp = state.get("input") or {}
    # Simulate a health check based on input flags
    requires_quarantine = inp.get("requires_quarantine", False)

    return {
        "log": [f"{UNISPSC_CODE}:health_clearance"],
        "health_status": "EXCELLENT" if not requires_quarantine else "HELD",
        "quarantine_verified": not requires_quarantine,
    }


def commodity_emit(state: State) -> dict[str, Any]:
    """Finalizes the commodity record and emits the result manifest."""
    is_ok = state.get("quarantine_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:commodity_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "lot_id": state.get("transport_lot_id"),
            "health": state.get("health_status"),
            "status": "READY_FOR_DISPATCH" if is_ok else "UNDER_REVIEW",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("intake", intake_validation)
_g.add_node("clearance", health_clearance)
_g.add_node("emit", commodity_emit)

_g.add_edge(START, "intake")
_g.add_edge("intake", "clearance")
_g.add_edge("clearance", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
