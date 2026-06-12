# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111050 — Fuel (segment 13).

Bespoke graph for Fuel logic, handling properties analysis,
safety verification, and batch release protocols.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111050"
UNISPSC_TITLE = "Fuel"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111050"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Fuel
    fuel_grade: str
    flash_point_celsius: float
    vapor_pressure_kpa: float
    batch_id: str
    is_safe: bool


def analyze_properties(state: State) -> dict[str, Any]:
    """Analyzes the physical and chemical properties of the fuel batch."""
    inp = state.get("input") or {}
    fuel_grade = inp.get("fuel_grade", "Standard")
    batch_id = inp.get("batch_id", "BATCH-000")

    # Simulate extraction of properties from input
    flash_point = inp.get("flash_point", 40.0)
    vapor_pressure = inp.get("vapor_pressure", 50.0)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_properties -> {fuel_grade} ({batch_id})"],
        "fuel_grade": fuel_grade,
        "batch_id": batch_id,
        "flash_point_celsius": flash_point,
        "vapor_pressure_kpa": vapor_pressure,
    }


def safety_verification(state: State) -> dict[str, Any]:
    """Verifies that fuel properties meet safety standards."""
    flash_point = state.get("flash_point_celsius", 0.0)
    # Simple safety check: flash point must be above 38 degrees for certain fuels
    is_safe = flash_point > 38.0

    return {
        "log": [f"{UNISPSC_CODE}:safety_verification -> safe={is_safe}"],
        "is_safe": is_safe,
    }


def release_batch(state: State) -> dict[str, Any]:
    """Finalizes the processing and releases the fuel batch for distribution."""
    is_safe = state.get("is_safe", False)
    batch_id = state.get("batch_id", "N/A")

    status = "RELEASED" if is_safe else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:release_batch -> {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "batch_id": batch_id,
            "status": status,
            "certified": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_properties", analyze_properties)
_g.add_node("safety_verification", safety_verification)
_g.add_node("release_batch", release_batch)

_g.add_edge(START, "analyze_properties")
_g.add_edge("analyze_properties", "safety_verification")
_g.add_edge("safety_verification", "release_batch")
_g.add_edge("release_batch", END)

graph = _g.compile()
