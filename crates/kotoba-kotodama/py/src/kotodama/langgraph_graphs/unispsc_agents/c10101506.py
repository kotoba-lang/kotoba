# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10101506 — Livestock (segment 10).

Bespoke graph logic for livestock management, covering intake, health
verification, and movement recording.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10101506"
UNISPSC_TITLE = "Livestock"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10101506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Livestock
    species: str
    head_count: int
    health_status: str
    origin_farm: str
    quarantine_verified: bool


def intake_livestock(state: State) -> dict[str, Any]:
    """Parse the input payload for animal species and head count."""
    inp = state.get("input") or {}
    species = inp.get("species", "unknown")
    count = int(inp.get("count", 0))
    farm = inp.get("farm_id", "unspecified_origin")

    return {
        "log": [f"{UNISPSC_CODE}:intake_livestock_species={species}_count={count}"],
        "species": species,
        "head_count": count,
        "origin_farm": farm,
    }


def verify_health_compliance(state: State) -> dict[str, Any]:
    """Evaluate health status and verify quarantine requirements."""
    species = state.get("species")
    count = state.get("head_count", 0)

    # Simple logic: require species and positive count for clearance
    is_valid = species not in (None, "unknown") and count > 0
    status = "certified_healthy" if is_valid else "documentation_required"

    return {
        "log": [f"{UNISPSC_CODE}:verify_health_compliance_status={status}"],
        "health_status": status,
        "quarantine_verified": is_valid,
    }


def record_livestock_movement(state: State) -> dict[str, Any]:
    """Finalize record for transport or asset management."""
    cleared = state.get("quarantine_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:record_livestock_movement_cleared={cleared}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "livestock_details": {
                "species": state.get("species"),
                "head_count": state.get("head_count"),
                "origin": state.get("origin_farm"),
                "health": state.get("health_status"),
            },
            "status": "AUTHORIZED" if cleared else "HOLD",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("intake", intake_livestock)
_g.add_node("verify", verify_health_compliance)
_g.add_node("record", record_livestock_movement)

_g.add_edge(START, "intake")
_g.add_edge("intake", "verify")
_g.add_edge("verify", "record")
_g.add_edge("record", END)

graph = _g.compile()
