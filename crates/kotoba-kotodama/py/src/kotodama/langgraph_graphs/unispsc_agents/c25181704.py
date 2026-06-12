# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25181704 — Trailer (segment 25).

Bespoke graph logic for trailer inventory management and safety verification.
Processes technical specifications including axle configuration and payload
capacity before finalizing the asset record.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25181704"
UNISPSC_TITLE = "Trailer"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25181704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Trailer
    axle_count: int
    payload_capacity_kg: float
    safety_inspection_passed: bool
    vin_verified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the physical specifications of the trailer asset."""
    inp = state.get("input") or {}
    axles = int(inp.get("axles", 2))
    capacity = float(inp.get("capacity_kg", 3500.0))
    vin = inp.get("vin", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "axle_count": axles,
        "payload_capacity_kg": capacity,
        "vin_verified": len(vin) == 17
    }


def safety_inspection(state: State) -> dict[str, Any]:
    """Simulates a safety check based on specs and VIN verification."""
    is_valid_vin = state.get("vin_verified", False)
    has_axles = state.get("axle_count", 0) > 0
    passed = is_valid_vin and has_axles

    return {
        "log": [f"{UNISPSC_CODE}:safety_inspection"],
        "safety_inspection_passed": passed
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Finalizes the trailer agent's state and prepares the result dictionary."""
    is_ok = state.get("safety_inspection_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "asset_data": {
                "axles": state.get("axle_count"),
                "capacity": state.get("payload_capacity_kg"),
                "vin_status": "verified" if state.get("vin_verified") else "invalid"
            },
            "status": "active" if is_ok else "quarantined",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("inspect", safety_inspection)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inspect")
_g.add_edge("inspect", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
