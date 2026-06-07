# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101612 — Ore Procurement (segment 11).

Bespoke graph logic for industrial ore acquisition, handling material
specifications, quantity verification, and procurement finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101612"
UNISPSC_TITLE = "Ore Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101612"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Ore Procurement domain state
    ore_type: str
    quantity_metric_tons: float
    assay_required: bool
    supplier_tier: int
    procurement_status: str


def initialize_procurement(state: State) -> dict[str, Any]:
    """Extracts procurement parameters from input."""
    inp = state.get("input") or {}
    ore = str(inp.get("ore", "Iron"))
    qty = float(inp.get("quantity", 1000.0))
    return {
        "log": [f"{UNISPSC_CODE}:initialize_procurement"],
        "ore_type": ore,
        "quantity_metric_tons": qty,
        "assay_required": qty > 500,
    }


def assess_supplier(state: State) -> dict[str, Any]:
    """Mocks supplier tier assignment based on quantity and ore type."""
    ore = state.get("ore_type", "Iron")
    # Strategic ores get higher tier scrutiny
    tier = 1 if ore in ["Copper", "Gold", "Lithium", "Cobalt"] else 2
    return {
        "log": [f"{UNISPSC_CODE}:assess_supplier"],
        "supplier_tier": tier,
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Generates the final procurement result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_order"],
        "procurement_status": "authorized",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "details": {
                "ore": state.get("ore_type"),
                "quantity": state.get("quantity_metric_tons"),
                "tier": state.get("supplier_tier"),
                "assay": state.get("assay_required"),
            },
            "status": "SUCCESS",
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_procurement)
_g.add_node("assess", assess_supplier)
_g.add_node("finalize", finalize_order)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
