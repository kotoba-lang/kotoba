# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121602 — Tanker (segment 25).

This module implements bespoke logic for the Tanker agent, managing the
lifecycle of maritime cargo transport including safety validation and loading.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121602"
UNISPSC_TITLE = "Tanker"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Tanker
    vessel_id: str
    cargo_type: str
    capacity_utilization: float
    safety_inspection_passed: bool


def validate_manifest(state: State) -> dict[str, Any]:
    """Validates the shipping manifest and identifies the tanker vessel."""
    inp = state.get("input") or {}
    vessel_id = inp.get("vessel_id", "T-9999")
    cargo_type = inp.get("cargo_type", "Crude Oil")

    return {
        "log": [f"{UNISPSC_CODE}:validate_manifest: {vessel_id} assigned for {cargo_type}"],
        "vessel_id": vessel_id,
        "cargo_type": cargo_type,
    }


def perform_safety_check(state: State) -> dict[str, Any]:
    """Simulates a hull and valve integrity inspection for the tanker."""
    # Logic: Basic validation that cargo volume doesn't exceed 100% capacity
    inp = state.get("input") or {}
    requested_vol = inp.get("volume", 50000)
    max_capacity = 60000

    passed = requested_vol <= max_capacity
    utilization = (requested_vol / max_capacity) * 100

    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_check: Passed={passed}"],
        "safety_inspection_passed": passed,
        "capacity_utilization": round(utilization, 2),
    }


def authorize_departure(state: State) -> dict[str, Any]:
    """Finalizes the tanker state and issues a clearance code."""
    passed = state.get("safety_inspection_passed", False)
    vessel = state.get("vessel_id", "Unknown")

    status = "CLEARED" if passed else "RETAINED_IN_PORT"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_departure: {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vessel_id": vessel,
            "status": status,
            "utilization": f"{state.get('capacity_utilization', 0)}%",
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_manifest", validate_manifest)
_g.add_node("perform_safety_check", perform_safety_check)
_g.add_node("authorize_departure", authorize_departure)

_g.add_edge(START, "validate_manifest")
_g.add_edge("validate_manifest", "perform_safety_check")
_g.add_edge("perform_safety_check", "authorize_departure")
_g.add_edge("authorize_departure", END)

graph = _g.compile()
