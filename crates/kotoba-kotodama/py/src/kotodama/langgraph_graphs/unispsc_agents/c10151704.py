# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151704 — Feed (segment 10).

This bespoke graph manages the lifecycle of animal feed batches, focusing on
composition validation, nutritional verification, and quality release.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151704"
UNISPSC_TITLE = "Feed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Feed
    batch_id: str
    feed_type: str
    nutritional_verified: bool
    moisture_content_pass: bool


def ingest_batch_metadata(state: State) -> dict[str, Any]:
    """Ingests and validates basic batch information."""
    inp = state.get("input") or {}
    batch_id = inp.get("batch_id", "B-000")
    feed_type = inp.get("feed_type", "general")
    return {
        "log": [f"{UNISPSC_CODE}:ingest_batch_metadata"],
        "batch_id": batch_id,
        "feed_type": feed_type,
    }


def verify_nutrition_profile(state: State) -> dict[str, Any]:
    """Simulates a nutritional analysis check for the feed batch."""
    # For Feed (10151704), we ensure the profile matches the intended species
    feed_type = state.get("feed_type")
    # Simulation: only specific types are considered verified in this model
    is_valid = feed_type in ["poultry", "swine", "cattle", "equine"]
    return {
        "log": [f"{UNISPSC_CODE}:verify_nutrition_profile"],
        "nutritional_verified": is_valid,
        "moisture_content_pass": True,  # Default success in simulation
    }


def authorize_release(state: State) -> dict[str, Any]:
    """Finalizes the processing and sets the result payload."""
    verified = state.get("nutritional_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:authorize_release"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_id"),
            "status": "RELEASED" if verified else "HOLD",
            "ok": verified,
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_batch_metadata)
_g.add_node("verify", verify_nutrition_profile)
_g.add_node("release", authorize_release)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "verify")
_g.add_edge("verify", "release")
_g.add_edge("release", END)

graph = _g.compile()
