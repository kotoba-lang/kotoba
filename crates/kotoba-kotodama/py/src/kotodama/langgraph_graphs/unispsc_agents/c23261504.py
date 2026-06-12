# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23261504 — Laser Machine (segment 23).

Bespoke implementation for industrial laser machining, including safety
interlock verification, optical path calibration, and assist-gas
management for precision cutting or engraving operations.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23261504"
UNISPSC_TITLE = "Laser Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23261504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Laser-specific domain state
    power_kw: float
    focal_length_mm: int
    assist_gas_type: str
    safety_interlock_verified: bool


def validate_safety_protocols(state: State) -> dict[str, Any]:
    """Ensures environment is safe for high-power laser emission."""
    inp = state.get("input") or {}
    power = float(inp.get("power", 1.5))

    # Requirement: High-intensity beams (>2.0kw) must have cooling confirmed
    cooling_ok = inp.get("cooling_active", True)
    safe = cooling_ok if power > 2.0 else True

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_protocols"],
        "power_kw": power,
        "safety_interlock_verified": safe,
    }


def calibrate_optical_path(state: State) -> dict[str, Any]:
    """Adjusts mirrors and lens position based on material thickness."""
    inp = state.get("input") or {}
    thickness = float(inp.get("material_thickness_mm", 5.0))

    # Calculate focal depth offset
    focal = 150 if thickness < 10 else 200
    gas = "Oxygen" if thickness > 8 else "Nitrogen"

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_optical_path"],
        "focal_length_mm": focal,
        "assist_gas_type": gas,
    }


def execute_machining_pass(state: State) -> dict[str, Any]:
    """Simulates the laser firing process and generates the final result."""
    is_safe = state.get("safety_interlock_verified", False)

    if not is_safe:
        return {
            "log": [f"{UNISPSC_CODE}:operation_halted_unsafe"],
            "result": {
                "ok": False,
                "error": "Safety interlock validation failed",
                "code": UNISPSC_CODE
            }
        }

    power = state.get("power_kw", 0.0)
    gas = state.get("assist_gas_type", "Air")

    return {
        "log": [f"{UNISPSC_CODE}:execute_machining_pass_complete"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "execution_metrics": {
                "peak_power_kw": power,
                "gas_medium": gas,
                "precision_alignment": True
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_safety", validate_safety_protocols)
_g.add_node("calibrate_optics", calibrate_optical_path)
_g.add_node("execute_pass", execute_machining_pass)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "calibrate_optics")
_g.add_edge("calibrate_optics", "execute_pass")
_g.add_edge("execute_pass", END)

graph = _g.compile()
