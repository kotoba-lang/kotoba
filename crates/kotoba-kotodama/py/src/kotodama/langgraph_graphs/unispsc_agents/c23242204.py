# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242204 — Lapping (segment 23).

Bespoke implementation for precision surface finishing processes. This agent
manages the state transitions for lapping operations, including workpiece
inspection, abrasive cycle execution, and final surface verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242204"
UNISPSC_TITLE = "Lapping"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242204"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Lapping
    target_roughness_microns: float
    current_roughness_microns: float
    abrasive_grit_size: int
    cycle_duration_seconds: int
    lap_plate_material: str


def inspect_workpiece(state: State) -> dict[str, Any]:
    """Initial assessment of the workpiece surface condition."""
    inp = state.get("input") or {}
    initial_roughness = inp.get("initial_roughness", 5.0)
    target = inp.get("target_roughness", 0.1)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_workpiece - initial roughness: {initial_roughness}μm"],
        "current_roughness_microns": initial_roughness,
        "target_roughness_microns": target,
        "lap_plate_material": inp.get("plate_material", "Cast Iron"),
        "abrasive_grit_size": inp.get("grit_size", 1200)
    }


def execute_lapping_cycle(state: State) -> dict[str, Any]:
    """Simulates the abrasive machining process to reduce surface roughness."""
    current = state.get("current_roughness_microns", 5.0)
    target = state.get("target_roughness_microns", 0.1)
    grit = state.get("abrasive_grit_size", 1200)

    # Simulate material removal and surface refinement
    # Higher grit size (finer) reduces roughness more slowly but to a better finish
    reduction_factor = 0.5 if grit > 1000 else 0.3
    new_roughness = max(target, current * (1 - reduction_factor))

    return {
        "log": [f"{UNISPSC_CODE}:execute_lapping_cycle - grit {grit} applied"],
        "current_roughness_microns": new_roughness,
        "cycle_duration_seconds": 300
    }


def verify_finish(state: State) -> dict[str, Any]:
    """Final metrology check against requirements."""
    current = state.get("current_roughness_microns", 0.0)
    target = state.get("target_roughness_microns", 0.1)
    success = current <= target

    return {
        "log": [f"{UNISPSC_CODE}:verify_finish - achieved {current:.4f}μm"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "final_roughness": current,
            "meets_specification": success,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_workpiece)
_g.add_node("process", execute_lapping_cycle)
_g.add_node("verify", verify_finish)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "process")
_g.add_edge("process", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
