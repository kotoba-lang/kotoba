# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112208 — Spray Kit (segment 24).

Bespoke graph logic for Spray Kit assembly, calibration, and safety validation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112208"
UNISPSC_TITLE = "Spray Kit"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112208"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Spray Kit
    nozzle_type: str
    tank_capacity_liters: float
    pressure_rating_psi: int
    is_fully_assembled: bool
    safety_check_passed: bool


def inspect_components(state: State) -> dict[str, Any]:
    """Checks for essential spray kit parts like nozzle and tank."""
    inp = state.get("input") or {}
    nozzle = inp.get("nozzle", "standard_cone")
    capacity = float(inp.get("capacity", 2.0))

    # Validation logic for assembly state
    has_nozzle = "nozzle" in inp or "nozzle_type" in inp
    has_tank = "tank" in inp or "capacity" in inp

    return {
        "log": [f"{UNISPSC_CODE}:inspect_components"],
        "nozzle_type": nozzle,
        "tank_capacity_liters": capacity,
        "is_fully_assembled": has_nozzle and has_tank,
    }


def calibrate_pressure(state: State) -> dict[str, Any]:
    """Simulates pressure calibration and safety threshold verification."""
    inp = state.get("input") or {}
    target_psi = int(inp.get("target_psi", 40))

    # Safety limit for standard spray kits is usually 60 PSI
    passed = 0 < target_psi <= 60

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_pressure"],
        "pressure_rating_psi": target_psi,
        "safety_check_passed": passed,
    }


def finalize_kit(state: State) -> dict[str, Any]:
    """Generates the final status and metadata for the Spray Kit agent."""
    is_assembled = state.get("is_fully_assembled", False)
    is_safe = state.get("safety_check_passed", False)
    success = is_assembled and is_safe

    return {
        "log": [f"{UNISPSC_CODE}:finalize_kit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "certified" if success else "failed_inspection",
            "details": {
                "nozzle": state.get("nozzle_type"),
                "capacity": state.get("tank_capacity_liters"),
                "pressure": state.get("pressure_rating_psi")
            },
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_components)
_g.add_node("calibrate", calibrate_pressure)
_g.add_node("finalize", finalize_kit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calibrate")
_g.add_edge("calibrate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
