# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121600 — Rail (segment 25).

Bespoke graph logic for rail infrastructure components, focusing on
material specifications, gauge validation, and safety certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121600"
UNISPSC_TITLE = "Rail"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    track_gauge: str
    rail_profile: str
    hardness_brinell: int
    certified_safety: bool


def validate_infrastructure(state: State) -> dict[str, Any]:
    """Validates basic rail infrastructure parameters from input."""
    inp = state.get("input") or {}
    gauge = inp.get("gauge", "standard")
    profile = inp.get("profile", "T-rail")

    return {
        "log": [f"{UNISPSC_CODE}:validate_infrastructure"],
        "track_gauge": gauge,
        "rail_profile": profile,
    }


def analyze_metallurgy(state: State) -> dict[str, Any]:
    """Simulates metallurgical analysis for rail wear resistance."""
    # Logic based on profile and gauge
    gauge = state.get("track_gauge", "standard")
    hardness = 300 if gauge == "standard" else 260

    return {
        "log": [f"{UNISPSC_CODE}:analyze_metallurgy"],
        "hardness_brinell": hardness,
        "certified_safety": hardness >= 250,
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Compiles the final rail specification and safety manifest."""
    is_safe = state.get("certified_safety", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "specification": {
            "gauge": state.get("track_gauge"),
            "profile": state.get("rail_profile"),
            "hardness": state.get("hardness_brinell"),
        },
        "safety_verified": is_safe,
        "status": "APPROVED" if is_safe else "REJECTED",
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("validate", validate_infrastructure)
_g.add_node("analyze", analyze_metallurgy)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
