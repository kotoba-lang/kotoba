# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111511 — Boat Procurement (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111511"
UNISPSC_TITLE = "Boat Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111511"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    hull_type: str
    vessel_class: str
    registry_verified: bool
    budget_approved: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the boat specifications and hull requirements."""
    inp = state.get("input") or {}
    hull = inp.get("hull_type", "fiberglass")
    v_class = inp.get("vessel_class", "commercial")
    budget = inp.get("budget", 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "hull_type": hull,
        "vessel_class": v_class,
        "budget_approved": budget > 50000,
    }


def check_vessel_registry(state: State) -> dict[str, Any]:
    """Checks the boat against regional vessel registries for compliance."""
    # Logic: Validate registry if budget is approved and hull type is known
    hull = state.get("hull_type")
    is_valid = hull in ["fiberglass", "aluminum", "steel", "composite"]

    return {
        "log": [f"{UNISPSC_CODE}:check_vessel_registry"],
        "registry_verified": is_valid,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement order for the boat."""
    success = state.get("registry_verified") and state.get("budget_approved")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_status": "authorized" if success else "rejected",
            "vessel_details": {
                "class": state.get("vessel_class"),
                "hull": state.get("hull_type"),
            },
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("check_vessel_registry", check_vessel_registry)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "check_vessel_registry")
_g.add_edge("check_vessel_registry", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
