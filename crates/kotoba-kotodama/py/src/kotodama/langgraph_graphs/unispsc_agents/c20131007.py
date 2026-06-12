# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20131007 — Transport.
Specialized logic for managing transport logistics, manifest validation, and route planning.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20131007"
UNISPSC_TITLE = "Transport"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20131007"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Transport
    cargo_manifest: list[str]
    route_plan: str
    is_hazardous: bool
    tracking_id: str


def validate_manifest(state: State) -> dict[str, Any]:
    """Validates the cargo manifest from the input."""
    inp = state.get("input") or {}
    cargo = inp.get("cargo", [])
    is_haz = any("chemical" in item.lower() or "fuel" in item.lower() for item in cargo)

    return {
        "log": [f"{UNISPSC_CODE}:validate_manifest"],
        "cargo_manifest": cargo,
        "is_hazardous": is_haz,
        "tracking_id": f"TRK-{UNISPSC_CODE}-{hash(str(cargo)) % 10000}"
    }


def plan_route(state: State) -> dict[str, Any]:
    """Generates a mock route plan based on the cargo type."""
    inp = state.get("input") or {}
    destination = inp.get("destination", "Central Depot")
    hazard_suffix = " (Hazardous Materials Route)" if state.get("is_hazardous") else ""

    return {
        "log": [f"{UNISPSC_CODE}:plan_route"],
        "route_plan": f"Direct to {destination}{hazard_suffix}"
    }


def finalize_transport(state: State) -> dict[str, Any]:
    """Finalizes the transport order and prepares the result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_transport"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tracking_id": state.get("tracking_id"),
            "route": state.get("route_plan"),
            "manifest_count": len(state.get("cargo_manifest", [])),
            "status": "DISPATCHED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_manifest", validate_manifest)
_g.add_node("plan_route", plan_route)
_g.add_node("finalize_transport", finalize_transport)

_g.add_edge(START, "validate_manifest")
_g.add_edge("validate_manifest", "plan_route")
_g.add_edge("plan_route", "finalize_transport")
_g.add_edge("finalize_transport", END)

graph = _g.compile()
