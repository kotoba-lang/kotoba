# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121600 — Paper (segment 14).
Bespoke logic for paper specification inspection and grade analysis.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121600"
UNISPSC_TITLE = "Paper"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Paper
    weight_gsm: float
    pulp_type: str
    opacity_percent: int
    is_recycled: bool
    batch_verified: bool


def inspect_specification(state: State) -> dict[str, Any]:
    """Inspects the paper specifications from the provided input state."""
    inp = state.get("input") or {}
    weight = inp.get("weight_gsm", 80.0)
    pulp = inp.get("pulp_type", "chemical")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_specification"],
        "weight_gsm": weight,
        "pulp_type": pulp,
        "is_recycled": inp.get("recycled", False),
    }


def analyze_grade(state: State) -> dict[str, Any]:
    """Determines the paper quality grade based on weight and composition."""
    weight = state.get("weight_gsm", 0.0)
    # Heuristic: heavier paper generally provides higher opacity
    opacity = 95 if weight > 90 else 85
    return {
        "log": [f"{UNISPSC_CODE}:analyze_grade"],
        "opacity_percent": opacity,
        "batch_verified": weight > 0,
    }


def register_batch(state: State) -> dict[str, Any]:
    """Finalizes the paper batch registration for inventory management."""
    verified = state.get("batch_verified", False)
    weight = state.get("weight_gsm", 0.0)
    pulp = state.get("pulp_type", "unknown")
    return {
        "log": [f"{UNISPSC_CODE}:register_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "certified" if verified else "pending",
            "metadata": {
                "gsm": weight,
                "pulp": pulp,
                "opacity": state.get("opacity_percent"),
                "recycled": state.get("is_recycled"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specification)
_g.add_node("analyze", analyze_grade)
_g.add_node("register", register_batch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "register")
_g.add_edge("register", END)

graph = _g.compile()
