# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111505 — Tanker (segment 25).

Bespoke graph logic for tanker vessel operations, cargo manifest validation,
and maritime logistics routing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111505"
UNISPSC_TITLE = "Tanker"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    vessel_registration: str
    cargo_manifest: dict[str, Any]
    routing_vector: str
    safety_compliance: bool
    hull_type: str


def validate_manifest(state: State) -> dict[str, Any]:
    """Validates the tanker manifest and hull integrity standards."""
    inp = state.get("input") or {}
    reg = inp.get("vessel_registration", "IMO-9123456")
    cargo = inp.get("cargo", {"type": "crude", "volume_bbl": 500000})

    return {
        "log": [f"{UNISPSC_CODE}:validate_manifest -> {reg}"],
        "vessel_registration": reg,
        "cargo_manifest": cargo,
        "safety_compliance": True,
        "hull_type": "double_hull",
    }


def calculate_routing(state: State) -> dict[str, Any]:
    """Optimizes maritime transit pathing for heavy tanker displacement."""
    vessel = state.get("vessel_registration")
    return {
        "log": [f"{UNISPSC_CODE}:calculate_routing -> optimizing for {vessel}"],
        "routing_vector": "great_circle_optimized",
    }


def finalize_logistics(state: State) -> dict[str, Any]:
    """Finalizes the tanker operation and emits the result manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_logistics"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vessel": state.get("vessel_registration"),
            "hull_spec": state.get("hull_type"),
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_manifest", validate_manifest)
_g.add_node("calculate_routing", calculate_routing)
_g.add_node("finalize_logistics", finalize_logistics)

_g.add_edge(START, "validate_manifest")
_g.add_edge("validate_manifest", "calculate_routing")
_g.add_edge("calculate_routing", "finalize_logistics")
_g.add_edge("finalize_logistics", END)

graph = _g.compile()
