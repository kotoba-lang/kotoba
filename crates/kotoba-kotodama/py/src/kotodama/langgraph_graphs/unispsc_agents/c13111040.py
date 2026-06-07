# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111040 — Ore (segment 13).

Bespoke graph logic for Ore processing workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111040"
UNISPSC_TITLE = "Ore"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111040"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Ore
    ore_type: str
    purity_level: float
    extraction_site: str
    weight_metric_tons: float
    assay_verified: bool


def inspect_batch(state: State) -> dict[str, Any]:
    """Inspects the raw ore batch and metadata."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:inspect_batch"],
        "ore_type": inp.get("ore_type", "Unknown"),
        "extraction_site": inp.get("site_id", "Default-Site-A"),
        "weight_metric_tons": float(inp.get("weight", 0.0)),
    }


def perform_assay(state: State) -> dict[str, Any]:
    """Simulates purity assay testing for the ore batch."""
    # Logic based on ore_type or weight
    ore_type = state.get("ore_type", "Unknown")
    purity = 0.85 if ore_type.lower() == "iron" else 0.42

    return {
        "log": [f"{UNISPSC_CODE}:perform_assay"],
        "purity_level": purity,
        "assay_verified": True if purity > 0.0 else False,
    }


def certify_yield(state: State) -> dict[str, Any]:
    """Finalizes the ore batch certification and results."""
    purity = state.get("purity_level", 0.0)
    weight = state.get("weight_metric_tons", 0.0)
    net_yield = weight * purity

    return {
        "log": [f"{UNISPSC_CODE}:certify_yield"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "net_yield_tons": net_yield,
            "status": "Certified" if purity > 0.1 else "Tailings",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_batch", inspect_batch)
_g.add_node("perform_assay", perform_assay)
_g.add_node("certify_yield", certify_yield)

_g.add_edge(START, "inspect_batch")
_g.add_edge("inspect_batch", "perform_assay")
_g.add_edge("perform_assay", "certify_yield")
_g.add_edge("certify_yield", END)

graph = _g.compile()
