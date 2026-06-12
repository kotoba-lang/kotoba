# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101709 — Conveyor (segment 24).
Bespoke logic for managing material handling conveyor systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101709"
UNISPSC_TITLE = "Conveyor"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101709"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    conveyor_speed_mps: float
    load_weight_kg: float
    belt_integrity_pct: int
    emergency_stop_active: bool


def inspect_safety(state: State) -> dict[str, Any]:
    """Inspects conveyor safety and initial load state."""
    inp = state.get("input") or {}
    speed = inp.get("target_speed", 1.2)
    weight = inp.get("load_weight", 0.0)

    # Simulate a safety check: max weight capacity is 500kg
    is_safe = weight < 500.0

    return {
        "log": [f"{UNISPSC_CODE}:inspect_safety - Weight: {weight}kg, Speed: {speed}m/s"],
        "conveyor_speed_mps": float(speed) if is_safe else 0.0,
        "load_weight_kg": float(weight),
        "belt_integrity_pct": 98,
        "emergency_stop_active": not is_safe,
    }


def transport_material(state: State) -> dict[str, Any]:
    """Simulates the material being moved across the conveyor belt."""
    if state.get("emergency_stop_active"):
        return {"log": [f"{UNISPSC_CODE}:transport_material - ABORTED: Emergency Stop active"]}

    speed = state.get("conveyor_speed_mps", 0.0)
    weight = state.get("load_weight_kg", 0.0)

    # Simulate slight wear and tear on the belt during operation
    current_integrity = state.get("belt_integrity_pct", 100)

    return {
        "log": [f"{UNISPSC_CODE}:transport_material - Transporting {weight}kg at {speed}m/s"],
        "belt_integrity_pct": current_integrity - 1,
    }


def finish_cycle(state: State) -> dict[str, Any]:
    """Finalizes the transport cycle and reports metrics."""
    is_stopped = state.get("emergency_stop_active", False)
    weight = state.get("load_weight_kg", 0.0)
    integrity = state.get("belt_integrity_pct", 100)

    return {
        "log": [f"{UNISPSC_CODE}:finish_cycle"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "STOPPED" if is_stopped else "COMPLETED",
            "throughput_kg": weight if not is_stopped else 0.0,
            "belt_condition": f"{integrity}%",
            "ok": not is_stopped,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_safety", inspect_safety)
_g.add_node("transport_material", transport_material)
_g.add_node("finish_cycle", finish_cycle)

_g.add_edge(START, "inspect_safety")
_g.add_edge("inspect_safety", "transport_material")
_g.add_edge("transport_material", "finish_cycle")
_g.add_edge("finish_cycle", END)

graph = _g.compile()
