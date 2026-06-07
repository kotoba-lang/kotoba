# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10141501 — Livestock.

This agent handles the lifecycle and data validation for live animals within
the agricultural supply chain, including health verification, herd identity,
and quarantine compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10141501"
UNISPSC_TITLE = "Livestock"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10141501"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for Livestock
    species: str
    health_status: str
    quarantine_verified: bool
    herd_id: str
    vaccination_status: str


def inspect_livestock(state: State) -> dict[str, Any]:
    """Initial inspection of the livestock data provided in the input."""
    inp = state.get("input") or {}
    species = inp.get("species", "unknown")
    herd_id = inp.get("herd_id", "unassigned")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_livestock: species={species}, herd={herd_id}"],
        "species": species,
        "herd_id": herd_id,
        "health_status": inp.get("health_status", "pending_review")
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Verify that the animal meets quarantine and vaccination requirements."""
    # Logic to simulate compliance check
    is_healthy = state.get("health_status") == "healthy"
    species = state.get("species")

    # Simple rule: certain species require specific vaccination check
    has_vaccines = state.get("input", {}).get("vaccines_cleared", False)

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance: checked {species}"],
        "quarantine_verified": is_healthy and has_vaccines,
        "vaccination_status": "verified" if has_vaccines else "missing"
    }


def register_livestock(state: State) -> dict[str, Any]:
    """Finalize the livestock record and produce the output result."""
    success = state.get("quarantine_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:register_livestock: final_status={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "species": state.get("species"),
            "herd_id": state.get("herd_id"),
            "verified": success,
            "status": "active_inventory" if success else "restricted"
        }
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_livestock)
_g.add_node("verify", verify_compliance)
_g.add_node("register", register_livestock)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "register")
_g.add_edge("register", END)

graph = _g.compile()
