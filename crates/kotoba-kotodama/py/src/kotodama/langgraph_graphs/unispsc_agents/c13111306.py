# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111306 — Mineral (segment 13).

Bespoke mineral processing graph logic for extraction, refining, and
inventory classification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111306"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111306"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Mineral
    ore_type: str
    purity_grade: float
    is_hazardous: bool
    extraction_site: str


def inspect_ore(state: State) -> dict[str, Any]:
    """Analyzes the raw input to determine mineral classification and origin."""
    inp = state.get("input") or {}
    ore = inp.get("ore_type", "unclassified_ore")
    site = inp.get("site", "remote_extraction_point")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_ore"],
        "ore_type": ore,
        "extraction_site": site,
    }


def refine_mineral(state: State) -> dict[str, Any]:
    """Simulates chemical/mechanical refining to determine purity and safety."""
    ore = state.get("ore_type", "")
    # Pure Python logic for refining simulation
    purity = 0.985 if "gold" in ore.lower() else 0.820
    hazardous = any(x in ore.lower() for x in ["uranium", "asbestos", "lead"])
    return {
        "log": [f"{UNISPSC_CODE}:refine_mineral"],
        "purity_grade": purity,
        "is_hazardous": hazardous,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Issues the final certificate of analysis and prepares inventory data."""
    purity = state.get("purity_grade", 0.0)
    haz = state.get("is_hazardous", False)
    ore = state.get("ore_type", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "composition": {
                "base_element": ore,
                "purity": f"{purity:.4f}",
                "hazard_warning": haz
            },
            "status": "certified"
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_ore)
_g.add_node("refine", refine_mineral)
_g.add_node("certify", certify_batch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "refine")
_g.add_edge("refine", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
