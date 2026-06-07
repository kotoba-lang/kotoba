# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101902 — Drum Grab (segment 24).

Bespoke graph logic for handling Drum Grab operations, replacing the
placeholder compliance pipeline. This agent manages load inspection,
clamping pressure regulation, and safety lock verification for
material handling equipment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101902"
UNISPSC_TITLE = "Drum Grab"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101902"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Drum Grab operations
    drum_material: str  # e.g., "steel", "poly", "fiber"
    clamping_psi: int
    safety_lock_engaged: bool
    load_weight_kg: float


def inspect_load(state: State) -> dict[str, Any]:
    """Node: Identify drum characteristics and initialize load parameters."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "steel")).lower()
    weight = float(inp.get("weight", 200.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_load(material={material}, weight={weight}kg)"],
        "drum_material": material,
        "load_weight_kg": weight,
        "safety_lock_engaged": False,
    }


def apply_tension(state: State) -> dict[str, Any]:
    """Node: Calculate and apply the required clamping pressure."""
    material = state.get("drum_material", "steel")
    weight = state.get("load_weight_kg", 0.0)

    # Calculate psi based on material fragility and load weight
    # Poly drums require lower pressure to prevent deformation
    base_psi = 1200 if material == "steel" else 700
    required_psi = int(base_psi + (weight * 0.45))

    return {
        "log": [f"{UNISPSC_CODE}:apply_tension(psi={required_psi})"],
        "clamping_psi": required_psi,
    }


def verify_and_lift(state: State) -> dict[str, Any]:
    """Node: Engage safety locks and prepare for vertical movement."""
    psi = state.get("clamping_psi", 0)
    material = state.get("drum_material", "steel")

    # Safety threshold check
    is_safe = psi > 400 if material != "poly" else psi > 300

    return {
        "log": [f"{UNISPSC_CODE}:verify_and_lift(lock_engaged={is_safe})"],
        "safety_lock_engaged": is_safe,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation_id": "DG-LIFT-EXEC",
            "status": "cleared_for_lift" if is_safe else "safety_abort",
            "telemetry": {
                "clamping_pressure": psi,
                "lock_status": "engaged" if is_safe else "failed"
            }
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_load)
_g.add_node("tension", apply_tension)
_g.add_node("verify", verify_and_lift)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "tension")
_g.add_edge("tension", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
