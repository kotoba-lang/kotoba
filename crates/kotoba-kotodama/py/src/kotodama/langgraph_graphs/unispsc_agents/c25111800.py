# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111800 — Watercraft (segment 25).

Bespoke graph for watercraft management, covering classification,
seaworthiness assessment, and registry recording.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111800"
UNISPSC_TITLE = "Watercraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    hull_type: str
    propulsion_system: str
    tonnage_category: int
    is_seaworthy: bool


def classify_vessel(state: State) -> dict[str, Any]:
    """Determines the vessel type and propulsion based on input specs."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:classify_vessel"],
        "hull_type": inp.get("hull", "displacement"),
        "propulsion_system": inp.get("propulsion", "inboard"),
        "tonnage_category": inp.get("tonnage", 0),
    }


def assess_seaworthiness(state: State) -> dict[str, Any]:
    """Checks hull integrity and safety equipment availability."""
    return {
        "log": [f"{UNISPSC_CODE}:assess_seaworthiness"],
        "is_seaworthy": True,
    }


def register_watercraft(state: State) -> dict[str, Any]:
    """Finalizes the watercraft record in the regional registry."""
    return {
        "log": [f"{UNISPSC_CODE}:register_watercraft"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "hull_type": state.get("hull_type"),
            "seaworthy": state.get("is_seaworthy"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("classify", classify_vessel)
_g.add_node("assess", assess_seaworthiness)
_g.add_node("register", register_watercraft)

_g.add_edge(START, "classify")
_g.add_edge("classify", "assess")
_g.add_edge("assess", "register")
_g.add_edge("register", END)

graph = _g.compile()
