# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153006 — Laser Welder.
Specialized logic for high-precision laser welding operations in segment 23.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153006"
UNISPSC_TITLE = "Laser Welder"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153006"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields
    material_thickness_mm: float
    beam_intensity_kw: float
    cooling_system_active: bool
    safety_interlock_secured: bool
    weld_integrity_score: float


def calibrate_laser(state: State) -> dict[str, Any]:
    """Sets initial laser parameters based on material specifications."""
    inp = state.get("input") or {}
    thickness = float(inp.get("thickness", 1.5))
    # Safety first: check cooling and interlocks
    cooling = inp.get("cooling_active", True)
    interlock = inp.get("interlock_engaged", True)

    # Calculate required power (toy model: 1.2kW per mm)
    power = thickness * 1.2

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_laser -> thickness={thickness}mm, power={power}kW"],
        "material_thickness_mm": thickness,
        "beam_intensity_kw": power,
        "cooling_system_active": cooling,
        "safety_interlock_secured": interlock,
    }


def execute_welding_cycle(state: State) -> dict[str, Any]:
    """Simulates the laser welding process if safety conditions are met."""
    if not state.get("cooling_system_active") or not state.get("safety_interlock_secured"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_welding_cycle -> SAFETY_FAULT"],
            "weld_integrity_score": 0.0,
        }

    # Simulate a successful weld based on power sufficiency
    power = state.get("beam_intensity_kw", 0.0)
    thickness = state.get("material_thickness_mm", 1.0)

    integrity = 0.98 if power >= (thickness * 1.1) else 0.45

    return {
        "log": [f"{UNISPSC_CODE}:execute_welding_cycle -> integrity={integrity}"],
        "weld_integrity_score": integrity,
    }


def finalize_weld_report(state: State) -> dict[str, Any]:
    """Aggregates the final state into the result dictionary."""
    integrity = state.get("weld_integrity_score", 0.0)
    success = integrity > 0.8

    return {
        "log": [f"{UNISPSC_CODE}:finalize_weld_report -> success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "COMPLETED" if success else "FAILED",
            "integrity_score": integrity,
            "did": UNISPSC_DID,
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("calibrate", calibrate_laser)
_g.add_node("weld", execute_welding_cycle)
_g.add_node("finalize", finalize_weld_report)

_g.add_edge(START, "calibrate")
_g.add_edge("calibrate", "weld")
_g.add_edge("weld", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
