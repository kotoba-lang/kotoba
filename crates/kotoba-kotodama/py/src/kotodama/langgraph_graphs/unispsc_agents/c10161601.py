# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10161601 — Livestock (segment 10).

Bespoke graph for livestock asset management, including quarantine
verification, health status tracking, and lot identification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161601"
UNISPSC_TITLE = "Livestock"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    livestock_kind: str
    health_status: str
    quarantine_verified: bool
    lot_id: str


def intake_livestock(state: State) -> dict[str, Any]:
    """Validates the input and extracts livestock metadata."""
    inp = state.get("input") or {}
    kind = inp.get("kind", "unspecified")
    lid = inp.get("lot_id", "unknown-lot")
    return {
        "log": [f"{UNISPSC_CODE}:intake_livestock: kind={kind} lot={lid}"],
        "livestock_kind": kind,
        "lot_id": lid,
    }


def assess_health(state: State) -> dict[str, Any]:
    """Assesses health status and checks quarantine requirements."""
    lid = state.get("lot_id", "unknown")
    # Simulation: lots with 'V' suffix are pre-verified for health/quarantine
    is_verified = lid.endswith("V")
    status = "healthy" if is_verified else "quarantine_pending"
    return {
        "log": [f"{UNISPSC_CODE}:assess_health: lot={lid} verified={is_verified}"],
        "health_status": status,
        "quarantine_verified": is_verified,
    }


def record_livestock(state: State) -> dict[str, Any]:
    """Produces the final record of the livestock asset entry."""
    kind = state.get("livestock_kind")
    status = state.get("health_status")
    verified = state.get("quarantine_verified")

    return {
        "log": [f"{UNISPSC_CODE}:record_livestock: final_status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "asset_record": {
                "kind": kind,
                "lot_id": state.get("lot_id"),
                "health_status": status,
                "quarantine_verified": verified,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("intake", intake_livestock)
_g.add_node("assess", assess_health)
_g.add_node("record", record_livestock)

_g.add_edge(START, "intake")
_g.add_edge("intake", "assess")
_g.add_edge("assess", "record")
_g.add_edge("record", END)

graph = _g.compile()
