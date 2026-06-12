# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10141601 — Feed.
This agent handles the lifecycle of animal feed specifications, nutrient analysis,
and batch formulation within the agricultural supply chain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10141601"
UNISPSC_TITLE = "Feed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10141601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields
    batch_id: str
    nutrient_profile: dict[str, float]
    moisture_content: float
    quality_verified: bool
    feed_type: str


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the incoming feed request and extracts basic metadata."""
    inp = state.get("input") or {}
    feed_type = inp.get("feed_type", "general_forage")
    batch_id = inp.get("batch_id", "PENDING_ID")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "feed_type": feed_type,
        "batch_id": batch_id,
        "quality_verified": False
    }


def analyze_nutrients(state: State) -> dict[str, Any]:
    """Simulates nutrient analysis of the feed batch."""
    # Dummy nutrient calculation based on feed type
    profile = {
        "crude_protein": 14.5,
        "crude_fat": 3.2,
        "fiber": 22.0
    }

    return {
        "log": [f"{UNISPSC_CODE}:analyze_nutrients"],
        "nutrient_profile": profile,
        "moisture_content": 12.5,
        "quality_verified": True
    }


def finalize_feed_record(state: State) -> dict[str, Any]:
    """Finalizes the feed record and prepares the output result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_feed_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_id"),
            "status": "ready_for_distribution" if state.get("quality_verified") else "held",
            "metadata": {
                "moisture": state.get("moisture_content"),
                "protein_content": state.get("nutrient_profile", {}).get("crude_protein")
            }
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("analyze", analyze_nutrients)
_g.add_node("finalize", finalize_feed_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
