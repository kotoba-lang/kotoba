# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11151715 — Ceramic (segment 11).

Bespoke graph logic for ceramic material processing and specification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151715"
UNISPSC_TITLE = "Ceramic"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151715"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    clay_body_type: str
    firing_temp_celsius: int
    kiln_atmosphere: str
    shaping_method: str
    is_bisque_fired: bool


def inspect_raw_materials(state: State) -> dict[str, Any]:
    """Inspects the input requirements for the ceramic production."""
    inp = state.get("input") or {}
    clay_type = inp.get("clay_type", "stoneware")
    method = inp.get("method", "wheel_thrown")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_materials"],
        "clay_body_type": clay_type,
        "shaping_method": method,
        "is_bisque_fired": False,
    }


def analyze_firing_profile(state: State) -> dict[str, Any]:
    """Determines optimal firing temperatures based on clay body."""
    clay = state.get("clay_body_type", "stoneware")
    temp = 1200
    atmosphere = "oxidizing"
    if clay == "porcelain":
        temp = 1300
        atmosphere = "reducing"
    elif clay == "earthenware":
        temp = 1050
    return {
        "log": [f"{UNISPSC_CODE}:analyze_firing_profile"],
        "firing_temp_celsius": temp,
        "kiln_atmosphere": atmosphere,
        "is_bisque_fired": True,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Finalizes the ceramic technical specification."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec": {
                "clay": state.get("clay_body_type"),
                "temp": state.get("firing_temp_celsius"),
                "method": state.get("shaping_method"),
                "status": "ready_for_glazing" if state.get("is_bisque_fired") else "raw"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_raw_materials)
_g.add_node("analyze", analyze_firing_profile)
_g.add_node("finalize", finalize_specification)
_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
