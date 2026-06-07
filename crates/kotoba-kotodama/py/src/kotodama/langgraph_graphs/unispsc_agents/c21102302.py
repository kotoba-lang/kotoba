# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102302 — Tiller (segment 21).

Bespoke logic for agricultural soil cultivation equipment management.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102302"
UNISPSC_TITLE = "Tiller"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102302"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Tiller
    soil_hardness: float
    target_depth_cm: int
    fuel_level_pct: float
    blades_inspected: bool


def inspect_equipment(state: State) -> dict[str, Any]:
    """Verifies mechanical integrity and fuel levels for the tiller."""
    inp = state.get("input") or {}
    fuel = float(inp.get("initial_fuel", 100.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_equipment"],
        "fuel_level_pct": fuel,
        "blades_inspected": True,
    }


def calibrate_cultivation(state: State) -> dict[str, Any]:
    """Calculates target depth based on soil hardness input."""
    inp = state.get("input") or {}
    hardness = float(inp.get("soil_hardness", 0.5))
    # Higher hardness leads to shallower initial pass
    depth = int(30 * (1.0 - (hardness * 0.5)))
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_cultivation"],
        "soil_hardness": hardness,
        "target_depth_cm": depth,
    }


def execute_tilling(state: State) -> dict[str, Any]:
    """Simulates the tilling operation and records the outcome."""
    fuel = state.get("fuel_level_pct", 0.0)
    depth = state.get("target_depth_cm", 0)
    success = fuel > 5.0 and state.get("blades_inspected", False)

    return {
        "log": [f"{UNISPSC_CODE}:execute_tilling"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "tilling_depth_cm": depth,
            "fuel_consumed": 2.5 if success else 0.0,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_equipment)
_g.add_node("calibrate", calibrate_cultivation)
_g.add_node("execute", execute_tilling)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calibrate")
_g.add_edge("calibrate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
