# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10131508 — Feed (segment 10).
Bespoke logic for feed batch processing, safety validation, and nutrient analysis.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10131508"
UNISPSC_TITLE = "Feed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10131508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Feed domain state
    feed_category: str
    nutrient_profile: dict[str, float]
    batch_identifier: str
    safety_audit_passed: bool
    quarantine_status: str


def validate_source(state: State) -> dict[str, Any]:
    """Validate the feed source and initialize batch data."""
    inp = state.get("input") or {}
    category = inp.get("category", "Standard Grain")
    batch = inp.get("batch_id", "F-LST-001")

    return {
        "log": [f"{UNISPSC_CODE}:validate_source - {category} batch {batch} initialized."],
        "feed_category": category,
        "batch_identifier": batch,
        "quarantine_status": "PENDING"
    }


def perform_analysis(state: State) -> dict[str, Any]:
    """Perform chemical and nutritional analysis on the feed batch."""
    inp = state.get("input") or {}
    # Simulated analysis logic based on provided moisture or defaults
    moisture = inp.get("measured_moisture", 12.5)
    contaminants = inp.get("toxin_level", 0.01)

    profile = {
        "protein_content": 16.5,
        "moisture_level": moisture,
        "contaminant_ppm": contaminants
    }

    # Safety thresholds: Moisture < 14%, Contaminants < 0.05 ppm
    is_safe = moisture < 14.0 and contaminants < 0.05

    return {
        "log": [f"{UNISPSC_CODE}:perform_analysis - Analysis complete. Safety: {is_safe}."],
        "nutrient_profile": profile,
        "safety_audit_passed": is_safe,
        "quarantine_status": "RELEASED" if is_safe else "REJECTED"
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Certify the batch and emit the final product record."""
    is_safe = state.get("safety_audit_passed", False)
    status = state.get("quarantine_status", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch - Production record finalized as {status}."],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_safe,
            "batch": state.get("batch_identifier"),
            "nutrients": state.get("nutrient_profile"),
            "quarantine_final": status,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_source", validate_source)
_g.add_node("perform_analysis", perform_analysis)
_g.add_node("certify_batch", certify_batch)

_g.add_edge(START, "validate_source")
_g.add_edge("validate_source", "perform_analysis")
_g.add_edge("perform_analysis", "certify_batch")
_g.add_edge("certify_batch", END)

graph = _g.compile()
