# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111531 — Natural gas driven generator.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111531"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111531"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for a Natural Gas Driven Generator
    fuel_pressure_psi: float
    engine_rpm: float
    power_output_kw: float
    grid_sync_stable: bool


def check_fuel_supply(state: State) -> dict[str, Any]:
    """Validates the natural gas supply pressure for the generator."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 45.0))

    return {
        "log": [f"{UNISPSC_CODE}:check_fuel_supply"],
        "fuel_pressure_psi": pressure,
        "grid_sync_stable": False,
    }


def engage_ignition(state: State) -> dict[str, Any]:
    """Starts the combustion cycle and ramps up engine RPM."""
    pressure = state.get("fuel_pressure_psi", 0.0)
    # Ignition requires minimum fuel pressure to sustain combustion
    rpm = 3600.0 if pressure > 20.0 else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:engage_ignition"],
        "engine_rpm": rpm,
    }


def synchronize_output(state: State) -> dict[str, Any]:
    """Adjusts voltage and synchronizes the generator to the local grid."""
    rpm = state.get("engine_rpm", 0.0)
    # Target power generation achieved at standard operating RPM
    power = 250.0 if rpm >= 3500.0 else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:synchronize_output"],
        "power_output_kw": power,
        "grid_sync_stable": power > 0,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "power_output_kw": power,
            "ok": power > 0,
        },
    }


_g = StateGraph(State)

_g.add_node("check_fuel_supply", check_fuel_supply)
_g.add_node("engage_ignition", engage_ignition)
_g.add_node("synchronize_output", synchronize_output)

_g.add_edge(START, "check_fuel_supply")
_g.add_edge("check_fuel_supply", "engage_ignition")
_g.add_edge("engage_ignition", "synchronize_output")
_g.add_edge("synchronize_output", END)

graph = _g.compile()
