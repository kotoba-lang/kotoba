# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26120000 — Harness (segment 26).

This agent manages the lifecycle of electrical harness assembly, providing
automated specification analysis, simulated electrical testing, and final
certification logic.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26120000"
UNISPSC_TITLE = "Harness"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26120000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Harness manufacturing
    voltage_rating: int
    connector_type: str
    is_shielded: bool
    continuity_verified: bool
    quality_score: float


def analyze_specs(state: State) -> dict[str, Any]:
    """Analyzes input parameters to determine harness design requirements."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:analyze_specs"],
        "voltage_rating": inp.get("voltage", 600),
        "connector_type": inp.get("connector", "Industrial-Circular"),
        "is_shielded": inp.get("shielded", True),
    }


def perform_electrical_test(state: State) -> dict[str, Any]:
    """Simulates continuity and insulation resistance testing."""
    is_shielded = state.get("is_shielded", False)
    voltage = state.get("voltage_rating", 0)

    # Simple heuristic for quality scoring
    score = 0.99 if is_shielded and voltage >= 600 else 0.88

    return {
        "log": [f"{UNISPSC_CODE}:perform_electrical_test"],
        "continuity_verified": True,
        "quality_score": score,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Issues the final certification result based on quality thresholds."""
    score = state.get("quality_score", 0.0)
    verified = state.get("continuity_verified", False)
    certified = verified and score > 0.85

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": certified,
            "quality_index": score,
            "connector_used": state.get("connector_type"),
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_specs)
_g.add_node("test", perform_electrical_test)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "test")
_g.add_edge("test", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
