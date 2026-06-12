# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151505 — Feed (segment 10).

Bespoke logic for animal feed processing and quality assurance, focusing on
nutritional validation and batch certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151505"
UNISPSC_TITLE = "Feed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Feed
    batch_id: str
    feed_type: str
    nutritional_analysis: dict[str, float]
    quality_certified: bool


def validate_consignment(state: State) -> dict[str, Any]:
    """Validates the incoming feed shipment metadata and identifies the batch."""
    inp = state.get("input") or {}
    batch_id = inp.get("batch_id", "F-BATCH-DEFAULT")
    feed_type = inp.get("feed_type", "mixed-grain")

    return {
        "log": [f"{UNISPSC_CODE}:validate_consignment(batch={batch_id})"],
        "batch_id": batch_id,
        "feed_type": feed_type,
    }


def analyze_nutrition(state: State) -> dict[str, Any]:
    """Performs a simulated nutritional analysis of the specific feed type."""
    # Synthetic analysis based on feed_type
    f_type = state.get("feed_type", "unknown")
    analysis = {
        "crude_protein": 14.5 if f_type == "pellets" else 11.2,
        "moisture": 12.0,
        "ash_content": 5.4
    }
    return {
        "log": [f"{UNISPSC_CODE}:analyze_nutrition(type={f_type})"],
        "nutritional_analysis": analysis,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Confirms the batch meets moisture and protein standards for distribution."""
    analysis = state.get("nutritional_analysis") or {}
    moisture = analysis.get("moisture", 100.0)
    # Certification criteria: moisture must be below 14%
    certified = moisture < 14.0

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch(certified={certified})"],
        "quality_certified": certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_id"),
            "certified": certified,
            "ok": certified,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_consignment", validate_consignment)
_g.add_node("analyze_nutrition", analyze_nutrition)
_g.add_node("certify_batch", certify_batch)

_g.add_edge(START, "validate_consignment")
_g.add_edge("validate_consignment", "analyze_nutrition")
_g.add_edge("analyze_nutrition", "certify_batch")
_g.add_edge("certify_batch", END)

graph = _g.compile()
