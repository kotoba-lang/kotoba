# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11151514 — Mineral (segment 11).

Bespoke graph logic for Mineral processing, including assay verification,
batch categorization, and origin certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151514"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151514"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Mineral
    mineral_type: str
    purity_grade: float
    is_certified: bool
    extraction_site: str


def assay_mineral(state: State) -> dict[str, Any]:
    """Analyzes the mineral properties and verifies purity levels."""
    inp = state.get("input") or {}
    m_type = inp.get("type", "unclassified_ore")
    purity = float(inp.get("purity", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:assay_mineral"],
        "mineral_type": m_type,
        "purity_grade": purity,
        "is_certified": purity > 0.85,  # High purity threshold
    }


def categorize_batch(state: State) -> dict[str, Any]:
    """Categorizes the mineral batch and records the extraction site."""
    inp = state.get("input") or {}
    site = inp.get("site", "remote_extraction_point")
    return {
        "log": [f"{UNISPSC_CODE}:categorize_batch"],
        "extraction_site": site,
    }


def certify_origin(state: State) -> dict[str, Any]:
    """Issues a final certification record for the mineral consignment."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_origin"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "details": {
                "type": state.get("mineral_type"),
                "purity": state.get("purity_grade"),
                "certified": state.get("is_certified"),
                "origin": state.get("extraction_site"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("assay_mineral", assay_mineral)
_g.add_node("categorize_batch", categorize_batch)
_g.add_node("certify_origin", certify_origin)

_g.add_edge(START, "assay_mineral")
_g.add_edge("assay_mineral", "categorize_batch")
_g.add_edge("categorize_batch", "certify_origin")
_g.add_edge("certify_origin", END)

graph = _g.compile()
