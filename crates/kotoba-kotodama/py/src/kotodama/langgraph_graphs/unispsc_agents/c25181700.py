# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25181700 — Trailer (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25181700"
UNISPSC_TITLE = "Trailer"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25181700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Trailer
    vin: str
    axle_count: int
    max_payload_kg: float
    safety_certified: bool


def inspect_trailer(state: State) -> dict[str, Any]:
    """Inspects the trailer input for identification and basic specifications."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:inspect_trailer"],
        "vin": str(inp.get("vin", "PENDING")),
        "axle_count": int(inp.get("axles", 2)),
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Performs a simulated safety check based on trailer specifications."""
    axles = state.get("axle_count", 0)
    # Simple logic: must have at least one axle to be considered a trailer
    is_safe = axles > 0
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "safety_certified": is_safe,
        "max_payload_kg": float(axles * 1500.0),
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Compiles the final trailer manifest and metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "vin": state.get("vin"),
            "safety": "APPROVED" if state.get("safety_certified") else "REJECTED",
            "capacity_kg": state.get("max_payload_kg"),
            "did": UNISPSC_DID,
            "status": "active",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_trailer)
_g.add_node("verify", verify_safety)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
