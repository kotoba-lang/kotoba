# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242607 — Finishing (segment 23).

This bespoke agent manages industrial finishing processes, including surface
preparation, coating application, and final quality inspection. It implements
the specific state transitions required for segment 23 (Industrial Manufacturing
and Processing Machinery and Accessories).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242607"
UNISPSC_TITLE = "Finishing"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242607"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific finishing fields
    surface_quality_score: float
    coating_type: str
    curing_time_minutes: int
    inspection_passed: bool


def prepare_surface(state: State) -> dict[str, Any]:
    """Validates the substrate and prepares the surface for finishing."""
    inp = state.get("input") or {}
    substrate = inp.get("substrate", "generic_metal")

    return {
        "log": [f"{UNISPSC_CODE}:prepare_surface_for_{substrate}"],
        "surface_quality_score": 0.85,  # Baseline quality after preparation
        "coating_type": inp.get("finish_type", "powder_coat"),
    }


def apply_finish(state: State) -> dict[str, Any]:
    """Simulates the application of the specified industrial coating."""
    coating = state.get("coating_type", "unspecified")
    # Industrial finishing parameters
    curing_time = 45 if "powder" in coating else 20

    return {
        "log": [f"{UNISPSC_CODE}:apply_{coating}_coating"],
        "curing_time_minutes": curing_time,
        "surface_quality_score": state.get("surface_quality_score", 0.0) + 0.12,
    }


def verify_and_emit(state: State) -> dict[str, Any]:
    """Final quality assurance check and result generation."""
    final_score = state.get("surface_quality_score", 0.0)
    passed = final_score > 0.90

    return {
        "log": [f"{UNISPSC_CODE}:final_qa_score_{final_score:.2f}"],
        "inspection_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "quality_audit": {
                "passed": passed,
                "score": final_score,
                "coating": state.get("coating_type"),
                "curing_cycle": state.get("curing_time_minutes")
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("prepare_surface", prepare_surface)
_g.add_node("apply_finish", apply_finish)
_g.add_node("verify_and_emit", verify_and_emit)

_g.add_edge(START, "prepare_surface")
_g.add_edge("prepare_surface", "apply_finish")
_g.add_edge("apply_finish", "verify_and_emit")
_g.add_edge("verify_and_emit", END)

graph = _g.compile()
