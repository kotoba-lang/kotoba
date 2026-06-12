# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24131502 — Cryo (segment 24).

Bespoke cryogenic equipment handling logic for industrial material conditioning.
This agent manages thermal stabilization cycles and containment integrity checks
for cryogenic storage and processing units.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24131502"
UNISPSC_TITLE = "Cryo"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24131502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Cryo handling
    target_temperature_kelvin: float
    current_vacuum_pressure: float
    nitrogen_level_percentage: float
    thermal_stability_achieved: bool
    safety_seal_status: str


def initialize_unit(state: State) -> dict[str, Any]:
    """Sets initial cryogenic parameters from input or defaults."""
    inp = state.get("input") or {}
    target = float(inp.get("target_temp", 77.0))  # Default to Liquid Nitrogen temp
    return {
        "log": [f"{UNISPSC_CODE}:initialize_unit - Target: {target}K"],
        "target_temperature_kelvin": target,
        "current_vacuum_pressure": 1e-4,
        "nitrogen_level_percentage": 100.0,
        "thermal_stability_achieved": False,
        "safety_seal_status": "LOCKED",
    }


def perform_cooldown(state: State) -> dict[str, Any]:
    """Simulates the thermal ramp-down and vacuum stabilization."""
    target = state.get("target_temperature_kelvin", 77.0)
    # Simulate a successful cooldown process
    return {
        "log": [f"{UNISPSC_CODE}:perform_cooldown - Cooling to {target}K"],
        "thermal_stability_achieved": True,
        "current_vacuum_pressure": 1e-6,
    }


def secure_containment(state: State) -> dict[str, Any]:
    """Finalizes the cryogenic state and emits the manifest."""
    is_stable = state.get("thermal_stability_achieved", False)
    pressure = state.get("current_vacuum_pressure", 0.0)

    ok = is_stable and pressure < 1e-5

    return {
        "log": [f"{UNISPSC_CODE}:secure_containment - Result: {'OK' if ok else 'FAIL'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "temp": state.get("target_temperature_kelvin"),
                "vacuum": pressure,
                "stability": is_stable
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize_unit", initialize_unit)
_g.add_node("perform_cooldown", perform_cooldown)
_g.add_node("secure_containment", secure_containment)

_g.add_edge(START, "initialize_unit")
_g.add_edge("initialize_unit", "perform_cooldown")
_g.add_edge("perform_cooldown", "secure_containment")
_g.add_edge("secure_containment", END)

graph = _g.compile()
