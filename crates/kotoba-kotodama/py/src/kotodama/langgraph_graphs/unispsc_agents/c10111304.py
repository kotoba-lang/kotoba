# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10111304 — Feed.

Bespoke graph for handling animal feed inventory and quality certification.
This agent manages the lifecycle of feed batches, ensuring nutritional
standards are met before dispatch.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10111304"
UNISPSC_TITLE = "Feed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10111304"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Feed
    feed_type: str
    nutrient_profile: dict[str, float]
    batch_id: str
    quality_certified: bool
    quarantine_check_passed: bool


def analyze_specifications(state: State) -> dict[str, Any]:
    """Analyzes incoming feed requirements and identifies the correct batch."""
    inp = state.get("input") or {}
    feed_type = inp.get("feed_type", "standard_forage")
    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications"],
        "feed_type": feed_type,
        "batch_id": f"LOT-{feed_type.upper()}-001",
    }


def verify_nutritional_compliance(state: State) -> dict[str, Any]:
    """Simulates a laboratory check of the feed's nutritional values."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_nutritional_compliance"],
        "nutrient_profile": {"protein": 18.5, "fiber": 12.0, "fat": 3.2},
        "quality_certified": True,
        "quarantine_check_passed": True,
    }


def dispatch_feed_lot(state: State) -> dict[str, Any]:
    """Finalizes the feed lot for transport and emits the actor response."""
    batch_id = state.get("batch_id", "UNKNOWN")
    return {
        "log": [f"{UNISPSC_CODE}:dispatch_feed_lot"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_dispatched": batch_id,
            "certified": state.get("quality_certified", False),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_specifications", analyze_specifications)
_g.add_node("verify_nutritional_compliance", verify_nutritional_compliance)
_g.add_node("dispatch_feed_lot", dispatch_feed_lot)

_g.add_edge(START, "analyze_specifications")
_g.add_edge("analyze_specifications", "verify_nutritional_compliance")
_g.add_edge("verify_nutritional_compliance", "dispatch_feed_lot")
_g.add_edge("dispatch_feed_lot", END)

graph = _g.compile()
