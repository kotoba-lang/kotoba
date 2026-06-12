# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101500 — Ag Machinery.

This module implements a bespoke state machine for agricultural machinery
processing, including specification validation, safety compliance checks,
and asset registration for segment 21.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101500"
UNISPSC_TITLE = "Ag Machinery"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    equipment_type: str
    safety_certification: bool
    operational_rating: float
    is_ready_for_deployment: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the physical specifications of the agricultural machinery."""
    inp = state.get("input") or {}
    eq_type = inp.get("type", "unknown_machinery")
    power = inp.get("horsepower", 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs:{eq_type}"],
        "equipment_type": eq_type,
        "operational_rating": min(1.0, power / 500.0) if power > 0 else 0.0,
    }


def check_safety_compliance(state: State) -> dict[str, Any]:
    """Verifies that the machinery meets regional safety standards."""
    rating = state.get("operational_rating", 0.0)
    compliant = rating > 0.1  # Simple heuristic for mock logic

    return {
        "log": [f"{UNISPSC_CODE}:check_safety_compliance:result={compliant}"],
        "safety_certification": compliant,
        "is_ready_for_deployment": compliant and rating >= 0.5,
    }


def register_asset(state: State) -> dict[str, Any]:
    """Finalizes the registration of the machinery in the asset management system."""
    ready = state.get("is_ready_for_deployment", False)
    eq_type = state.get("equipment_type", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:register_asset:finalized"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "asset_id": f"AG-{eq_type.upper()}-001",
            "status": "deployed" if ready else "pending_review",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("check_safety_compliance", check_safety_compliance)
_g.add_node("register_asset", register_asset)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "check_safety_compliance")
_g.add_edge("check_safety_compliance", "register_asset")
_g.add_edge("register_asset", END)

graph = _g.compile()
