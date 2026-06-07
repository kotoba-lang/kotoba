# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202404 — Aircraft (segment 25).

Bespoke logic for aircraft fleet management, airworthiness verification,
and payload-to-range performance calculations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202404"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202404"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Aircraft
    tail_number: str
    airworthiness_status: str
    payload_weight_kg: float
    estimated_range_km: float


def inspect_aircraft(state: State) -> dict[str, Any]:
    """Validates aircraft identification and maintenance readiness."""
    inp = state.get("input") or {}
    tail = inp.get("tail_number", "N-UNKNOWN")
    # Simulate airworthiness check based on maintenance clearance flag
    is_ready = inp.get("maintenance_clearance", False)
    status = "READY" if is_ready else "GROUNDED"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_aircraft tail={tail} status={status}"],
        "tail_number": tail,
        "airworthiness_status": status,
    }


def calculate_performance(state: State) -> dict[str, Any]:
    """Calculates operational range based on provided payload weight."""
    inp = state.get("input") or {}
    weight = float(inp.get("payload_weight_kg", 0.0))

    # Simple heuristic: base range of 4500km, reduced by 1km per 5kg of payload
    base_range = 4500.0
    range_penalty = weight / 5.0
    final_range = max(0.0, base_range - range_penalty)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_performance payload={weight}kg range={final_range}km"],
        "payload_weight_kg": weight,
        "estimated_range_km": final_range,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Consolidates findings into the final result manifest."""
    is_ok = state.get("airworthiness_status") == "READY"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest ok={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "manifest": {
                "tail_number": state.get("tail_number"),
                "status": state.get("airworthiness_status"),
                "range_estimate": state.get("estimated_range_km"),
                "payload": state.get("payload_weight_kg"),
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_aircraft", inspect_aircraft)
_g.add_node("calculate_performance", calculate_performance)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "inspect_aircraft")
_g.add_edge("inspect_aircraft", "calculate_performance")
_g.add_edge("calculate_performance", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
