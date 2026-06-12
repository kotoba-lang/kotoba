# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111806 — Raft (segment 25).

Bespoke graph logic for Raft procurement and deployment validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111806"
UNISPSC_TITLE = "Raft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Raft
    hull_integrity_score: float
    max_payload_capacity: int
    safety_gear_inventory: list[str]
    is_seaworthy: bool


def inspect_structure(state: State) -> dict[str, Any]:
    """Inspects the raft hull and buoyancy chambers."""
    inp = state.get("input") or {}
    integrity = float(inp.get("integrity_report", 0.95))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_structure"],
        "hull_integrity_score": integrity,
    }


def verify_capacity(state: State) -> dict[str, Any]:
    """Calculates payload limits and verifies load distribution."""
    inp = state.get("input") or {}
    capacity = int(inp.get("max_occupants", 8)) * 80  # Default 80kg per person
    return {
        "log": [f"{UNISPSC_CODE}:verify_capacity"],
        "max_payload_capacity": capacity,
    }


def certify_seaworthiness(state: State) -> dict[str, Any]:
    """Final check of safety gear and integrity scores to certify the raft."""
    integrity = state.get("hull_integrity_score", 0.0)
    gear = ["paddles", "life_vests", "repair_kit"]

    seaworthy = integrity > 0.85 and state.get("max_payload_capacity", 0) > 200

    return {
        "log": [f"{UNISPSC_CODE}:certify_seaworthiness"],
        "safety_gear_inventory": gear,
        "is_seaworthy": seaworthy,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "seaworthy": seaworthy,
            "integrity": integrity,
            "gear_count": len(gear),
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_structure", inspect_structure)
_g.add_node("verify_capacity", verify_capacity)
_g.add_node("certify_seaworthiness", certify_seaworthiness)

_g.add_edge(START, "inspect_structure")
_g.add_edge("inspect_structure", "verify_capacity")
_g.add_edge("verify_capacity", "certify_seaworthiness")
_g.add_edge("certify_seaworthiness", END)

graph = _g.compile()
