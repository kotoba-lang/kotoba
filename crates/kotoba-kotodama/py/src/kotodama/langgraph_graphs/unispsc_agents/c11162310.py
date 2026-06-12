# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162310 — Petrochem (segment 11).

Bespoke graph logic for petrochemical batch processing, refinement simulation,
and quality verification for transport safety.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162310"
UNISPSC_TITLE = "Petrochem"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162310"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Petrochem domain fields
    batch_serial_number: str
    octane_rating: float
    sulfur_content_ppm: float
    refinery_unit_id: str
    is_safe_for_transport: bool


def validate_feedstock(state: State) -> dict[str, Any]:
    """Inspects the raw petrochemical feedstock input and extracts batch metadata."""
    inp = state.get("input") or {}
    serial = inp.get("serial", "BATCH-PETRO-DEFAULT")
    octane = float(inp.get("octane", 87.0))
    unit = inp.get("unit_id", "REF-01")

    return {
        "log": [f"{UNISPSC_CODE}:validate_feedstock -> {serial} at {unit}"],
        "batch_serial_number": serial,
        "octane_rating": octane,
        "refinery_unit_id": unit,
    }


def simulate_refinement(state: State) -> dict[str, Any]:
    """Simulates the refining process by calculating sulfur reduction based on octane targets."""
    octane = state.get("octane_rating", 87.0)
    # Mock calculation: simulate sulfur content based on processing intensity
    # Higher octane usually requires more desulfurization effort in this mock model
    sulfur = max(2.5, 45.0 - (octane - 80) * 1.5)

    return {
        "log": [f"{UNISPSC_CODE}:simulate_refinement (octane={octane})"],
        "sulfur_content_ppm": sulfur,
    }


def verify_quality_standards(state: State) -> dict[str, Any]:
    """Final check on sulfur limits and volatility for international petrochemical standards."""
    sulfur = state.get("sulfur_content_ppm", 100.0)
    # Ultra-low sulfur standards are typically below 10-15 ppm
    safe = sulfur < 15.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_quality_standards (safe={safe})"],
        "is_safe_for_transport": safe,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "batch_serial": state.get("batch_serial_number"),
            "refinery_unit": state.get("refinery_unit_id"),
            "measured_sulfur_ppm": round(sulfur, 2),
            "transport_verified": safe,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_feedstock)
_g.add_node("refine", simulate_refinement)
_g.add_node("verify", verify_quality_standards)

_g.add_edge(START, "validate")
_g.add_edge("validate", "refine")
_g.add_edge("refine", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
