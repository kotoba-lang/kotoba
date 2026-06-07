# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101602 — Mineral (segment 11).

Bespoke logic for mineral sample processing, assay verification, and
inventory registration. This graph manages the state transitions for
mineralogical analysis within the Etz Hayyim actor framework.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101602"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    mineral_category: str
    assay_purity: float
    site_location_id: str
    is_certified: bool


def inspect_sample(state: State) -> dict[str, Any]:
    """Validates the incoming mineral sample metadata."""
    inp = state.get("input") or {}
    category = inp.get("category", "unclassified")
    site = inp.get("site_id", "unknown-source")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_sample: {category} from {site}"],
        "mineral_category": category,
        "site_location_id": site,
    }


def verify_assay(state: State) -> dict[str, Any]:
    """Simulates chemical analysis and purity verification."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.0))
    certified = purity > 0.85  # Standard threshold for industrial minerals

    return {
        "log": [f"{UNISPSC_CODE}:verify_assay: purity {purity:.2%}"],
        "assay_purity": purity,
        "is_certified": certified,
    }


def register_batch(state: State) -> dict[str, Any]:
    """Finalizes the batch record for the mineral inventory."""
    return {
        "log": [f"{UNISPSC_CODE}:register_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "category": state.get("mineral_category"),
            "certified": state.get("is_certified"),
            "status": "archived" if state.get("is_certified") else "pending_review",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_sample", inspect_sample)
_g.add_node("verify_assay", verify_assay)
_g.add_node("register_batch", register_batch)

_g.add_edge(START, "inspect_sample")
_g.add_edge("inspect_sample", "verify_assay")
_g.add_edge("verify_assay", "register_batch")
_g.add_edge("register_batch", END)

graph = _g.compile()
