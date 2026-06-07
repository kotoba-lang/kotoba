# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101102 — Motor Procurement (segment 26).
Bespoke LangGraph implementation for technical specification review,
supplier tier selection, and procurement finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101102"
UNISPSC_TITLE = "Motor Procurement"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101102"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Motor Procurement
    specifications_verified: bool
    supplier_tier: int
    procurement_priority: str
    delivery_estimate_days: int


def review_specs(state: State) -> dict[str, Any]:
    """Evaluates motor horsepower and voltage requirements."""
    inp = state.get("input") or {}
    horsepower = inp.get("horsepower", 0)
    voltage = inp.get("voltage", 0)

    # Simple validation logic
    verified = horsepower > 0 and voltage > 0
    priority = "EXPEDITED" if inp.get("urgent") or horsepower > 500 else "STANDARD"

    return {
        "log": [f"{UNISPSC_CODE}:review_specs:verified={verified}"],
        "specifications_verified": verified,
        "procurement_priority": priority,
    }


def identify_supplier(state: State) -> dict[str, Any]:
    """Selects supplier tier based on procurement priority."""
    priority = state.get("procurement_priority", "STANDARD")

    # Logic for sourcing strategy
    if priority == "EXPEDITED":
        tier = 1
        days = 3
    else:
        tier = 2
        days = 12

    return {
        "log": [f"{UNISPSC_CODE}:identify_supplier:tier={tier}"],
        "supplier_tier": tier,
        "delivery_estimate_days": days,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final procurement record and status."""
    verified = state.get("specifications_verified", False)
    tier = state.get("supplier_tier", 0)
    days = state.get("delivery_estimate_days", 0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_confirmed": verified,
            "execution_meta": {
                "supplier_tier": tier,
                "lead_time": f"{days} days",
                "verified": verified
            },
            "ok": verified,
        },
    }


_g = StateGraph(State)

_g.add_node("review_specs", review_specs)
_g.add_node("identify_supplier", identify_supplier)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "review_specs")
_g.add_edge("review_specs", "identify_supplier")
_g.add_edge("identify_supplier", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
