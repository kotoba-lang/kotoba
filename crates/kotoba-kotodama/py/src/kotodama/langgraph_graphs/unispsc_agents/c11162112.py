# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162112 — Metal (segment 11).

This agent provides bespoke logic for processing and validating metal ore
and natural mineral resources within the Etz Hayyim UNISPSC ecosystem.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162112"
UNISPSC_TITLE = "Metal"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162112"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Metal / Ore processing
    ore_type: str
    purity_level: float
    smelting_point: int
    is_hazardous: bool
    batch_authenticated: bool


def analyze_ore(state: State) -> dict[str, Any]:
    """Inspects the raw input for ore characteristics and mineral type."""
    inp = state.get("input") or {}
    ore = inp.get("ore_type", "unclassified")
    hazard = inp.get("is_hazardous", False)
    return {
        "log": [f"{UNISPSC_CODE}:analyze_ore:{ore}"],
        "ore_type": ore,
        "is_hazardous": hazard,
    }


def evaluate_purity(state: State) -> dict[str, Any]:
    """Calculates purity levels and smelting requirements based on ore type."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity_level", 0.0))
    # Synthetic logic for smelting point based on purity and mineral type
    base_point = 1200 if state.get("ore_type") != "iron" else 1538
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_purity:{purity}"],
        "purity_level": purity,
        "smelting_point": int(base_point * (1.1 if purity > 0.9 else 1.0)),
        "batch_authenticated": purity > 0.5,
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Finalizes the metadata and generates the result object for the metal batch."""
    auth = state.get("batch_authenticated", False)
    is_safe = not state.get("is_hazardous", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset:auth={auth}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metal_properties": {
                "ore_type": state.get("ore_type"),
                "purity": state.get("purity_level"),
                "smelting_point": state.get("smelting_point"),
                "hazardous": not is_safe,
            },
            "authenticated": auth,
            "ok": auth and is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_ore", analyze_ore)
_g.add_node("evaluate_purity", evaluate_purity)
_g.add_node("finalize_asset", finalize_asset)

_g.add_edge(START, "analyze_ore")
_g.add_edge("analyze_ore", "evaluate_purity")
_g.add_edge("evaluate_purity", "finalize_asset")
_g.add_edge("finalize_asset", END)

graph = _g.compile()
