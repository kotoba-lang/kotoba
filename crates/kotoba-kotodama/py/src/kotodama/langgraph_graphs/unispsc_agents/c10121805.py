# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10121805 — Feed (segment 10).

Bespoke implementation for Feed management and verification within the Live Plant
and Animal Material segment. This agent handles intake inspection, nutrient
profile validation, and batch certification for specialized feeds.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10121805"
UNISPSC_TITLE = "Feed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10121805"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Feed
    batch_id: str
    nutrient_profile: dict[str, float]
    safety_certified: bool
    feed_type: str


def intake_inspection(state: State) -> dict[str, Any]:
    """Inspects the incoming feed material for basic characteristics and tracking."""
    inp = state.get("input") or {}
    batch_id = str(inp.get("batch_id", "F-DEFAULT-001"))
    feed_type = str(inp.get("feed_type", "Grain"))

    return {
        "log": [f"{UNISPSC_CODE}:intake_inspection -> {batch_id} ({feed_type})"],
        "batch_id": batch_id,
        "feed_type": feed_type,
    }


def nutrition_validation(state: State) -> dict[str, Any]:
    """Validates the nutrient profile against required standards for animal health."""
    inp = state.get("input") or {}
    # Default profile if not provided in input
    profile = inp.get("nutrients", {"protein": 14.5, "fiber": 4.2, "fat": 3.1})

    # Logic: ensure protein meets minimum thresholds for Segment 10 (Animal Feed)
    protein_level = profile.get("protein", 0.0)
    is_valid = protein_level >= 12.0

    return {
        "log": [f"{UNISPSC_CODE}:nutrition_validation -> protein={protein_level}% {'PASSED' if is_valid else 'FAILED'}"],
        "nutrient_profile": profile,
        "safety_certified": is_valid,
    }


def batch_certification(state: State) -> dict[str, Any]:
    """Finalizes the certification of the feed batch and generates the result object."""
    is_safe = state.get("safety_certified", False)
    batch_id = state.get("batch_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:batch_certification -> status={'CERTIFIED' if is_safe else 'REJECTED'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": batch_id,
            "certification_status": "VALID" if is_safe else "INVALID",
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("intake_inspection", intake_inspection)
_g.add_node("nutrition_validation", nutrition_validation)
_g.add_node("batch_certification", batch_certification)

_g.add_edge(START, "intake_inspection")
_g.add_edge("intake_inspection", "nutrition_validation")
_g.add_edge("nutrition_validation", "batch_certification")
_g.add_edge("batch_certification", END)

graph = _g.compile()
