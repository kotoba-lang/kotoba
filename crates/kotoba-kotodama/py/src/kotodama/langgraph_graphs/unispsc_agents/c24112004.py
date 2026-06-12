# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112004 — Bin Procurement (segment 24).

This bespoke implementation handles the procurement workflow for industrial,
waste, and storage bins, including specification validation and cost estimation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112004"
UNISPSC_TITLE = "Bin Procurement"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields
    bin_category: str
    material_requirement: str
    quantity: int
    estimated_cost: float
    procurement_verified: bool


def validate_requirement(state: State) -> dict[str, Any]:
    """Validates the bin procurement request parameters."""
    inp = state.get("input") or {}
    category = inp.get("category", "Industrial Storage")
    qty = int(inp.get("quantity", 1))

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirement"],
        "bin_category": category,
        "quantity": qty,
        "procurement_verified": qty > 0
    }


def specify_materials(state: State) -> dict[str, Any]:
    """Determines material requirements based on the bin category."""
    category = state.get("bin_category", "Industrial Storage")

    # Simple mapping logic for bin materials
    material = "HDPE"
    if "Waste" in category:
        material = "Galvanized Steel"
    elif "Chemical" in category:
        material = "Stainless Steel"

    return {
        "log": [f"{UNISPSC_CODE}:specify_materials"],
        "material_requirement": material
    }


def estimate_procurement_cost(state: State) -> dict[str, Any]:
    """Calculates the estimated cost and finalizes the procurement result."""
    qty = state.get("quantity", 0)
    material = state.get("material_requirement", "Unknown")

    # Mock unit pricing based on material
    unit_prices = {
        "HDPE": 45.0,
        "Galvanized Steel": 120.0,
        "Stainless Steel": 350.0
    }
    price = unit_prices.get(material, 50.0)
    total = price * qty

    return {
        "log": [f"{UNISPSC_CODE}:estimate_procurement_cost"],
        "estimated_cost": total,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_summary": {
                "category": state.get("bin_category"),
                "material": material,
                "quantity": qty,
                "total_estimate": total
            },
            "status": "Ready for RFQ" if state.get("procurement_verified") else "Invalid Request"
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requirement)
_g.add_node("specify", specify_materials)
_g.add_node("estimate", estimate_procurement_cost)

_g.add_edge(START, "validate")
_g.add_edge("validate", "specify")
_g.add_edge("specify", "estimate")
_g.add_edge("estimate", END)

graph = _g.compile()
