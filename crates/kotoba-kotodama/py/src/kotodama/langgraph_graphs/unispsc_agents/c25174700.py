# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174700 — Cycle (segment 25).

This module provides a bespoke LangGraph implementation for managing the
lifecycle of a Cycle vehicle, including chassis configuration, safety
testing, and inventory finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174700"
UNISPSC_TITLE = "Cycle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Cycle (Vehicle segment)
    cycle_type: str
    frame_material: str
    safety_test_score: float
    is_street_legal: bool


def configure_chassis(state: State) -> dict[str, Any]:
    """Initializes the cycle configuration based on input specifications."""
    inp = state.get("input") or {}
    c_type = inp.get("type", "bicycle")
    material = inp.get("material", "aluminum")

    return {
        "log": [f"{UNISPSC_CODE}:configure_chassis:{c_type}:{material}"],
        "cycle_type": c_type,
        "frame_material": material,
    }


def perform_safety_check(state: State) -> dict[str, Any]:
    """Simulates a safety and structural integrity inspection for the cycle."""
    c_type = state.get("cycle_type", "unknown")
    # Simulation logic: bicycles are generally street legal, motorcycles require higher scores
    score = 0.96 if c_type == "bicycle" else 0.89

    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_check:score={score}"],
        "safety_test_score": score,
        "is_street_legal": score > 0.90 or c_type == "bicycle",
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Finalizes the vehicle record and prepares the dispatch result."""
    is_legal = state.get("is_street_legal", False)
    c_type = state.get("cycle_type", "generic")
    material = state.get("frame_material", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vehicle_specs": {
                "type": c_type,
                "material": material,
                "legal": is_legal
            },
            "status": "ready_for_dispatch" if is_legal else "quarantined",
        },
    }


_g = StateGraph(State)
_g.add_node("configure_chassis", configure_chassis)
_g.add_node("perform_safety_check", perform_safety_check)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "configure_chassis")
_g.add_edge("configure_chassis", "perform_safety_check")
_g.add_edge("perform_safety_check", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
