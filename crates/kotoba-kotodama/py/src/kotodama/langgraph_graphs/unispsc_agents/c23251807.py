# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251807 — Stamp (segment 23).
Bespoke graph for industrial marking and labeling equipment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251807"
UNISPSC_TITLE = "Stamp"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251807"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Stamp (Industrial marking)
    inscription_content: str
    base_material: str
    inking_system: str
    quality_threshold: float
    is_ready: bool


def analyze_marking_request(state: State) -> dict[str, Any]:
    """Analyzes the incoming marking request for a bespoke industrial stamp."""
    inp = state.get("input") or {}
    content = inp.get("content", "STAMP_23251807")
    material = inp.get("material", "standard_rubber")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_marking_request"],
        "inscription_content": content,
        "base_material": material,
        "quality_threshold": 0.95,
    }


def determine_mechanics(state: State) -> dict[str, Any]:
    """Selects the appropriate inking and mechanical system for the stamp."""
    material = state.get("base_material", "")

    system = "self_inking"
    if "metal" in material.lower():
        system = "manual_impact"
    elif "precision" in material.lower():
        system = "pre_inked_polymer"

    return {
        "log": [f"{UNISPSC_CODE}:determine_mechanics"],
        "inking_system": system,
        "is_ready": True,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Generates the final manufacturing specification for the stamp agent."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec": {
                "content": state.get("inscription_content"),
                "material": state.get("base_material"),
                "system": state.get("inking_system"),
                "confidence": state.get("quality_threshold"),
                "ready": state.get("is_ready"),
            },
            "status": "PROCESSED",
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_marking_request)
_g.add_node("mechanics", determine_mechanics)
_g.add_node("finalize", finalize_specification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "mechanics")
_g.add_edge("mechanics", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
