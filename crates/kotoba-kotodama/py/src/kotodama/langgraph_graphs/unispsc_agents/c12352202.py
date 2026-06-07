# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352202 — Aluminum (segment 12).

Bespoke logic for handling aluminum material state, purity verification,
and batch property calculation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352202"
UNISPSC_TITLE = "Aluminum"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352202"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Aluminum
    alloy_grade: str
    purity_percent: float
    batch_weight_kg: float
    specification_compliance: bool


def validate_metallurgy(state: State) -> dict[str, Any]:
    """Inspects raw material properties for aluminum standards."""
    inp = state.get("input") or {}
    alloy = str(inp.get("alloy_grade", "1100"))
    purity = float(inp.get("purity", 99.0))

    # Simple validation logic for aluminum purity
    is_compliant = purity >= 99.0 if alloy.startswith("1") else purity >= 90.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_metallurgy"],
        "alloy_grade": alloy,
        "purity_percent": purity,
        "specification_compliance": is_compliant,
    }


def calculate_yield(state: State) -> dict[str, Any]:
    """Calculates potential yield and batch characteristics."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))

    # Process batch logic
    log_msg = f"{UNISPSC_CODE}:calculate_yield weight={weight}"

    return {
        "log": [log_msg],
        "batch_weight_kg": weight,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Certifies the aluminum batch for inventory or shipment."""
    compliance = state.get("specification_compliance", False)
    alloy = state.get("alloy_grade", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified_alloy": alloy,
            "status": "APPROVED" if compliance else "REJECTED",
            "ok": compliance,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_metallurgy", validate_metallurgy)
_g.add_node("calculate_yield", calculate_yield)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "validate_metallurgy")
_g.add_edge("validate_metallurgy", "calculate_yield")
_g.add_edge("calculate_yield", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
