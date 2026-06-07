# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191502 — G S E Support (segment 25).

Bespoke logic for Ground Support Equipment (GSE) support operations, including
inventory validation, safety inspection, and deployment authorization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191502"
UNISPSC_TITLE = "G S E Support"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for GSE Support
    asset_id: str
    maintenance_status: str
    fuel_level: float
    safety_cleared: bool


def validate_inventory(state: State) -> dict[str, Any]:
    """Check if the requested GSE asset is in the local inventory registry."""
    inp = state.get("input") or {}
    asset_id = inp.get("asset_id", "GSE-GENERIC-01")
    return {
        "log": [f"{UNISPSC_CODE}:validate_inventory:{asset_id}"],
        "asset_id": asset_id,
        "maintenance_status": "INSPECTION_REQUIRED",
    }


def perform_safety_check(state: State) -> dict[str, Any]:
    """Verify fuel levels and safety protocols for the ground support equipment."""
    # Simulation: ensure asset is ready for flight-line support
    fuel = 0.85
    is_cleared = fuel > 0.15
    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_check:cleared={is_cleared}"],
        "fuel_level": fuel,
        "safety_cleared": is_cleared,
        "maintenance_status": "READY" if is_cleared else "REFUEL_OR_REPAIR",
    }


def authorize_deployment(state: State) -> dict[str, Any]:
    """Finalize the support request and mark the GSE for immediate deployment."""
    cleared = state.get("safety_cleared", False)
    return {
        "log": [f"{UNISPSC_CODE}:authorize_deployment"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "asset_id": state.get("asset_id"),
            "status": "DEPLOYED" if cleared else "GROUNDED",
            "did": UNISPSC_DID,
            "ok": cleared,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_inventory)
_g.add_node("inspect", perform_safety_check)
_g.add_node("authorize", authorize_deployment)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inspect")
_g.add_edge("inspect", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
