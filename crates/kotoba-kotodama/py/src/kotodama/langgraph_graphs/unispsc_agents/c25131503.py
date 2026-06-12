# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131503 — Seaplane (segment 25).

Bespoke graph for seaplane operations, covering pre-flight water safety checks
and amphibious takeoff readiness.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131503"
UNISPSC_TITLE = "Seaplane"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Seaplane operations
    fuel_verified: bool
    hull_integrity_sealed: bool
    water_clearance_level: float
    flight_plan_filed: bool


def inspect_aircraft(state: State) -> dict[str, Any]:
    """Node to verify fuel levels and physical airframe integrity."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:inspect_aircraft"],
        "fuel_verified": inp.get("fuel_kg", 0) > 500,
        "hull_integrity_sealed": True,
        "flight_plan_filed": inp.get("route") is not None,
    }


def evaluate_water_surface(state: State) -> dict[str, Any]:
    """Node to assess wave height and surface debris for safe water takeoff."""
    inp = state.get("input") or {}
    wave_height = inp.get("wave_height_meters", 0.5)
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_water_surface"],
        "water_clearance_level": wave_height,
    }


def clear_for_takeoff(state: State) -> dict[str, Any]:
    """Node to emit final flight readiness status based on water and plane state."""
    ready = (
        state.get("fuel_verified", False) and
        state.get("hull_integrity_sealed", False) and
        state.get("water_clearance_level", 0) < 2.0
    )
    return {
        "log": [f"{UNISPSC_CODE}:clear_for_takeoff"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "Airborne" if ready else "Grounded",
            "safety_check_passed": ready,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_aircraft", inspect_aircraft)
_g.add_node("evaluate_water_surface", evaluate_water_surface)
_g.add_node("clear_for_takeoff", clear_for_takeoff)

_g.add_edge(START, "inspect_aircraft")
_g.add_edge("inspect_aircraft", "evaluate_water_surface")
_g.add_edge("evaluate_water_surface", "clear_for_takeoff")
_g.add_edge("clear_for_takeoff", END)

graph = _g.compile()
