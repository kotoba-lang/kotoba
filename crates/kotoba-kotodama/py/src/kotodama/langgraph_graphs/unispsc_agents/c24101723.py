# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101723 — Roller Procurement.
Bespoke implementation for material handling equipment procurement processes.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101723"
UNISPSC_TITLE = "Roller Procurement"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101723"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Roller Procurement
    load_capacity_tons: float
    roller_material: str
    procurement_id: str
    compliance_verified: bool
    inventory_status: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the roller specifications from the input request."""
    inp = state.get("input") or {}
    capacity = float(inp.get("capacity", 2.5))
    material = inp.get("material", "hardened_steel")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "load_capacity_tons": capacity,
        "roller_material": material,
        "compliance_verified": capacity > 0,
    }


def assess_procurement_risk(state: State) -> dict[str, Any]:
    """Evaluates supply chain risk and confirms vendor availability."""
    material = state.get("roller_material", "unknown")
    # Simulation: specific materials have higher lead times or scarcity
    status = "available" if material != "rare_alloy" else "backordered"

    return {
        "log": [f"{UNISPSC_CODE}:assess_procurement_risk"],
        "inventory_status": status,
        "procurement_id": f"ROLL-PROC-{UNISPSC_CODE}-X01",
    }


def generate_procurement_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and prepares the actor result."""
    is_valid = state.get("compliance_verified", False)
    is_available = state.get("inventory_status") == "available"
    success = is_valid and is_available

    return {
        "log": [f"{UNISPSC_CODE}:generate_procurement_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "procurement_id": state.get("procurement_id"),
            "status": "processed" if success else "failed",
            "details": {
                "material": state.get("roller_material"),
                "capacity_tons": state.get("load_capacity_tons"),
                "inventory": state.get("inventory_status"),
            },
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("assess_risk", assess_procurement_risk)
_g.add_node("generate_order", generate_procurement_order)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess_risk")
_g.add_edge("assess_risk", "generate_order")
_g.add_edge("generate_order", END)

graph = _g.compile()
