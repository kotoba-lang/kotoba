# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13101701 — Petroleum (segment 13).

This bespoke LangGraph agent manages the lifecycle of Petroleum assets,
handling crude inspection, refinement classification, and quality certification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13101701"
UNISPSC_TITLE = "Petroleum"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13101701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Petroleum domain fields
    api_gravity: float
    sulfur_content: float
    viscosity_index: int
    refinement_stage: str
    certification_stamp: str


def inspect_crude(state: State) -> dict[str, Any]:
    """Perform initial chemical analysis of the petroleum batch."""
    inp = state.get("input") or {}
    gravity = inp.get("api_gravity", 35.0)
    sulfur = inp.get("sulfur_content", 0.4)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_crude"],
        "api_gravity": gravity,
        "sulfur_content": sulfur,
        "viscosity_index": inp.get("viscosity_index", 95),
    }


def classify_refinement(state: State) -> dict[str, Any]:
    """Determine the refinement stage based on API gravity and sulfur content."""
    gravity = state.get("api_gravity", 0.0)
    sulfur = state.get("sulfur_content", 0.0)

    # Classification logic: Sweet vs Sour, Light vs Heavy
    sweetness = "Sweet" if sulfur < 0.5 else "Sour"
    density = "Light" if gravity > 31.1 else "Heavy" if gravity < 22.3 else "Medium"

    stage = f"{density} {sweetness} Crude"
    return {
        "log": [f"{UNISPSC_CODE}:classify_refinement"],
        "refinement_stage": stage,
    }


def certify_quality(state: State) -> dict[str, Any]:
    """Finalize the asset record with a quality certification stamp."""
    stage = state.get("refinement_stage", "Unclassified")
    stamp = f"CERT-PETRO-{UNISPSC_CODE}-OK"

    return {
        "log": [f"{UNISPSC_CODE}:certify_quality"],
        "certification_stamp": stamp,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "classification": stage,
            "quality_stamp": stamp,
            "status": "Verified",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_crude", inspect_crude)
_g.add_node("classify_refinement", classify_refinement)
_g.add_node("certify_quality", certify_quality)

_g.add_edge(START, "inspect_crude")
_g.add_edge("inspect_crude", "classify_refinement")
_g.add_edge("classify_refinement", "certify_quality")
_g.add_edge("certify_quality", END)

graph = _g.compile()
