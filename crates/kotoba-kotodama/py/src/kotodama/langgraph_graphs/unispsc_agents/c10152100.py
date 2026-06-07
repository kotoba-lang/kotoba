# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10152100 — Raw Material.
Bespoke logic for handling base industrial or biological materials before processing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10152100"
UNISPSC_TITLE = "Raw Material"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10152100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    batch_origin: str
    quality_score: float
    purity_verified: bool
    safety_documentation: bool


def inspect_origin(state: State) -> dict[str, Any]:
    """Node: Inspect the source and batch data for the raw material."""
    inp = state.get("input") or {}
    origin = inp.get("origin", "unknown")
    has_docs = inp.get("has_safety_docs", False)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_origin: {origin}"],
        "batch_origin": origin,
        "safety_documentation": has_docs,
    }


def assess_quality(state: State) -> dict[str, Any]:
    """Node: Assess the quality and purity based on input parameters."""
    inp = state.get("input") or {}
    purity = inp.get("purity_percentage", 0.0)
    score = 1.0 if purity > 95.0 else 0.5

    return {
        "log": [f"{UNISPSC_CODE}:assess_quality: score {score}"],
        "quality_score": score,
        "purity_verified": purity > 90.0,
    }


def certify_material(state: State) -> dict[str, Any]:
    """Node: Finalize certification and emit the result package."""
    is_ok = state.get("purity_verified", False) and state.get("safety_documentation", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_material: certified={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "origin": state.get("batch_origin"),
            "quality": state.get("quality_score"),
            "certified": is_ok,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_origin", inspect_origin)
_g.add_node("assess_quality", assess_quality)
_g.add_node("certify_material", certify_material)

_g.add_edge(START, "inspect_origin")
_g.add_edge("inspect_origin", "assess_quality")
_g.add_edge("assess_quality", "certify_material")
_g.add_edge("certify_material", END)

graph = _g.compile()
