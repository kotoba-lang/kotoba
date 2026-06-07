# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15111701 — Aviation Fuel (segment 15).

Bespoke graph logic for handling aviation fuel specifications, safety
verification, and manifest generation. This agent ensures that fuel
batches meet required octane and flash point safety thresholds before
authorizing distribution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15111701"
UNISPSC_TITLE = "Aviation Fuel"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15111701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Aviation Fuel
    octane_rating: float
    flash_point_celsius: float
    is_certified: bool
    batch_id: str


def inspect_fuel_specs(state: State) -> dict[str, Any]:
    """Extracts fuel specifications and batch identifiers from input data."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:inspect_fuel_specs"],
        "octane_rating": float(inp.get("octane", 0.0)),
        "flash_point_celsius": float(inp.get("flash_point", 0.0)),
        "batch_id": str(inp.get("batch_id", "TMP-BATCH-001")),
    }


def verify_safety_standards(state: State) -> dict[str, Any]:
    """Verifies if the fuel batch meets minimum aviation safety standards."""
    # Example logic: Jet fuel typically requires a flash point above 38°C
    flash_point = state.get("flash_point_celsius", 0.0)
    octane = state.get("octane_rating", 0.0)

    # Simple validation: flash point > 38 and non-zero octane
    safe = flash_point >= 38.0 and octane > 0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_standards:safe={safe}"],
        "is_certified": safe,
    }


def generate_fuel_manifest(state: State) -> dict[str, Any]:
    """Generates the final dispatch manifest and certification result."""
    is_certified = state.get("is_certified", False)
    batch_id = state.get("batch_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:generate_fuel_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "batch_id": batch_id,
            "certified": is_certified,
            "status": "APPROVED" if is_certified else "REJECTED",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_fuel_specs", inspect_fuel_specs)
_g.add_node("verify_safety_standards", verify_safety_standards)
_g.add_node("generate_fuel_manifest", generate_fuel_manifest)

_g.add_edge(START, "inspect_fuel_specs")
_g.add_edge("inspect_fuel_specs", "verify_safety_standards")
_g.add_edge("verify_safety_standards", "generate_fuel_manifest")
_g.add_edge("generate_fuel_manifest", END)

graph = _g.compile()
