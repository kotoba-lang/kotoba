# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101905 — A T V (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101905"
UNISPSC_TITLE = "A T V"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101905"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for All Terrain Vehicles (ATV)
    engine_displacement_cc: int
    drive_system: str
    safety_rating: float
    is_ready_for_dispatch: bool


def assess_mechanics(state: State) -> dict[str, Any]:
    """Inspects the mechanical specifications of the ATV."""
    inp = state.get("input") or {}
    cc = inp.get("displacement", 500)
    drive = inp.get("drive_type", "4x4")

    return {
        "log": [f"{UNISPSC_CODE}:assess_mechanics"],
        "engine_displacement_cc": cc,
        "drive_system": drive
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Calculates a safety rating based on displacement and drive system."""
    cc = state.get("engine_displacement_cc", 0)
    drive = state.get("drive_system", "")

    # Basic logic: 4x4 systems are generally rated higher for stability
    rating = 0.85 if drive == "4x4" else 0.65
    if cc > 800 and drive != "4x4":
        rating -= 0.20

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "safety_rating": round(max(0.0, rating), 2)
    }


def finalize_status(state: State) -> dict[str, Any]:
    """Determines if the vehicle is ready based on safety rating."""
    rating = state.get("safety_rating", 0.0)
    ready = rating >= 0.5

    return {
        "log": [f"{UNISPSC_CODE}:finalize_status"],
        "is_ready_for_dispatch": ready,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "safety_score": rating,
            "dispatch_ready": ready,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("assess_mechanics", assess_mechanics)
_g.add_node("verify_safety", verify_safety)
_g.add_node("finalize_status", finalize_status)

_g.add_edge(START, "assess_mechanics")
_g.add_edge("assess_mechanics", "verify_safety")
_g.add_edge("verify_safety", "finalize_status")
_g.add_edge("finalize_status", END)

graph = _g.compile()
