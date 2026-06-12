# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101803 — Processor (segment 22).

This bespoke agent implements a domain-specific control flow for a heavy
construction material processor, managing hydraulic systems and jaw
apertures for demolition or aggregate reduction.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101803"
UNISPSC_TITLE = "Processor"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Segment 22 "Processor" (Construction Machinery)
    hydraulic_pressure_psi: int
    jaw_opening_mm: int
    blade_integrity_pct: float
    material_type: str
    safety_interlock_active: bool


def initialize_hydraulics(state: State) -> dict[str, Any]:
    """Initialize processor hydraulic systems and check safety interlocks."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:initialize_hydraulics"],
        "safety_interlock_active": True,
        "hydraulic_pressure_psi": int(inp.get("base_pressure", 2500)),
        "blade_integrity_pct": 98.5,
    }


def adjust_aperture(state: State) -> dict[str, Any]:
    """Configure jaw opening based on target material dimensions."""
    inp = state.get("input") or {}
    material = inp.get("material", "concrete_rubble")
    # Tougher materials require tighter initial jaw positioning
    target_aperture = 150 if material == "steel_rebar" else 400
    return {
        "log": [f"{UNISPSC_CODE}:adjust_aperture"],
        "material_type": material,
        "jaw_opening_mm": target_aperture,
    }


def execute_processing_cycle(state: State) -> dict[str, Any]:
    """Simulate the material processing/shearing cycle."""
    pressure = state.get("hydraulic_pressure_psi", 0)
    integrity = state.get("blade_integrity_pct", 0.0)

    # Success depends on sufficient pressure and blade condition
    success = pressure >= 2000 and integrity > 50.0
    return {
        "log": [f"{UNISPSC_CODE}:execute_processing_cycle"],
        "result": {
            "cycle_complete": success,
            "throughput_tons": 4.5 if success else 0.0,
        }
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Consolidate run data and emit final actor state."""
    cycle_data = state.get("result") or {}
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            **cycle_data,
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "machine_status": "STANDBY",
            "ok": cycle_data.get("cycle_complete", False),
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_hydraulics)
_g.add_node("configure", adjust_aperture)
_g.add_node("process", execute_processing_cycle)
_g.add_node("emit", finalize_telemetry)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "configure")
_g.add_edge("configure", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
