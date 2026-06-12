# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181507 — Conveyor (segment 23).
Bespoke logic for industrial conveyor systems monitoring and control.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181507"
UNISPSC_TITLE = "Conveyor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    belt_speed_mps: float
    load_weight_kg: float
    operational_status: str
    item_count: int


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the conveyor operating specifications from input."""
    inp = state.get("input") or {}
    speed = float(inp.get("target_speed", 0.5))
    capacity = float(inp.get("max_capacity", 100.0))

    log_msg = f"{UNISPSC_CODE}:validate_specs -> speed={speed}mps, capacity={capacity}kg"
    return {
        "log": [log_msg],
        "belt_speed_mps": speed,
        "operational_status": "ready" if speed > 0 else "idle",
        "item_count": 0
    }


def simulate_load(state: State) -> dict[str, Any]:
    """Simulates loading items onto the conveyor belt."""
    inp = state.get("input") or {}
    simulated_load = float(inp.get("current_load", 25.5))
    simulated_count = int(inp.get("batch_size", 10))

    speed = state.get("belt_speed_mps", 0.0)
    status = "running" if speed > 0 else "stopped"

    log_msg = f"{UNISPSC_CODE}:simulate_load -> load={simulated_load}kg, count={simulated_count}"
    return {
        "log": [log_msg],
        "load_weight_kg": simulated_load,
        "item_count": state.get("item_count", 0) + simulated_count,
        "operational_status": status
    }


def finalize_operation(state: State) -> dict[str, Any]:
    """Finalizes the conveyor operation and reports metrics."""
    efficiency = 0.98

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "metrics": {
            "final_item_count": state.get("item_count"),
            "load_kg": state.get("load_weight_kg"),
            "speed_mps": state.get("belt_speed_mps"),
            "status": state.get("operational_status"),
            "efficiency_rating": efficiency
        },
        "ok": True,
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_operation"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("simulate_load", simulate_load)
_g.add_node("finalize_operation", finalize_operation)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "simulate_load")
_g.add_edge("simulate_load", "finalize_operation")
_g.add_edge("finalize_operation", END)

graph = _g.compile()
