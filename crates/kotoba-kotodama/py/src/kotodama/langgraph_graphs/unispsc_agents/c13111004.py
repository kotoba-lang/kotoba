# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111004 — Mineral (segment 13).

Bespoke graph logic for mineral specimen analysis, assay processing, and
certification. This agent manages state transitions for the identification,
purity verification, and safety rating of mineral substances.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111004"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Mineral
    composition: str
    purity: float
    extraction_site: str
    safety_rating: str


def analyze_specimen(state: State) -> dict[str, Any]:
    """Validates incoming mineral data and identifies the primary composition."""
    inp = state.get("input") or {}
    comp = inp.get("mineral_type", "Standard Aggregate")
    site = inp.get("source_quarry", "Domestic-01")
    return {
        "log": [f"{UNISPSC_CODE}:analyze_specimen:identified:{comp}"],
        "composition": comp,
        "extraction_site": site,
    }


def perform_assay(state: State) -> dict[str, Any]:
    """Simulates a chemical assay to determine purity and safety grade."""
    # Heuristic: premium sources yield higher purity
    site = state.get("extraction_site", "")
    purity = 0.995 if "Premium" in site else 0.880
    rating = "Grade-A" if purity > 0.95 else "Grade-B"

    return {
        "log": [f"{UNISPSC_CODE}:perform_assay:purity:{purity:.3f}"],
        "purity": purity,
        "safety_rating": rating,
    }


def certify_mineral(state: State) -> dict[str, Any]:
    """Finalizes the processing by issuing a digital certification record."""
    rating = state.get("safety_rating", "Unknown")
    is_compliant = rating == "Grade-A"

    return {
        "log": [f"{UNISPSC_CODE}:certify_mineral:certified:{rating}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "composition": state.get("composition"),
                "site": state.get("extraction_site"),
                "purity": state.get("purity"),
                "rating": rating,
            },
            "status": "Certified" if is_compliant else "Restricted",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_specimen", analyze_specimen)
_g.add_node("perform_assay", perform_assay)
_g.add_node("certify_mineral", certify_mineral)

_g.add_edge(START, "analyze_specimen")
_g.add_edge("analyze_specimen", "perform_assay")
_g.add_edge("perform_assay", "certify_mineral")
_g.add_edge("certify_mineral", END)

graph = _g.compile()
