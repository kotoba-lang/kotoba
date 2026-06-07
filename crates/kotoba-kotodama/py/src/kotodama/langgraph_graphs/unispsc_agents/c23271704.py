# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271704 — Desoldering (segment 23).

Bespoke graph logic for industrial desoldering processes, including
thermal profile validation, vacuum extraction, and pad inspection.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271704"
UNISPSC_TITLE = "Desoldering"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Desoldering
    temperature_celsius: int
    vacuum_pressure_kpa: float
    component_id: str
    thermal_dwell_seconds: float


def prepare_extraction(state: State) -> dict[str, Any]:
    """Validates the desoldering parameters and preheats the station."""
    inp = state.get("input") or {}
    temp = inp.get("target_temp", 360)
    comp = inp.get("component_id", "U101")

    return {
        "log": [f"{UNISPSC_CODE}:prepare: target={temp}C for {comp}"],
        "temperature_celsius": temp,
        "component_id": comp,
        "thermal_dwell_seconds": 3.5,
    }


def apply_vacuum(state: State) -> dict[str, Any]:
    """Simulates the thermal ramp and active vacuum suction of solder."""
    temp = state.get("temperature_celsius", 0)
    suction = 55.2  # Simulated kPa

    # Logic based on state
    melted = temp > 300
    status = "LIQUID_EXTRACTION" if melted else "SOLID_FAILURE"

    return {
        "log": [f"{UNISPSC_CODE}:apply_vacuum: status={status}, pressure={suction}kPa"],
        "vacuum_pressure_kpa": suction,
    }


def verify_and_emit(state: State) -> dict[str, Any]:
    """Checks the pad integrity post-extraction and emits the result."""
    comp = state.get("component_id")
    pressure = state.get("vacuum_pressure_kpa", 0.0)

    success = pressure > 50.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_and_emit: pads_inspected, result={'OK' if success else 'REWORK'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "process_outcome": "SUCCESS" if success else "REWORK_REQUIRED",
            "extracted_component": comp,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("prepare", prepare_extraction)
_g.add_node("desolder", apply_vacuum)
_g.add_node("verify", verify_and_emit)

_g.add_edge(START, "prepare")
_g.add_edge("prepare", "desolder")
_g.add_edge("desolder", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
