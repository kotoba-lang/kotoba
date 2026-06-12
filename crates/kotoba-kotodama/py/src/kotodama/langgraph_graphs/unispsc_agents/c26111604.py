# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111604 — Generator (segment 26).

Bespoke graph logic for electrical power generation equipment. This agent
models the inspection, load testing, and operational reporting of a
generator unit, ensuring system stability and thermal compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111604"
UNISPSC_TITLE = "Generator"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific generator state
    power_rating_kva: float
    fuel_pressure_psi: float
    governor_frequency_hz: float
    alternator_winding_temp_c: float
    is_synchronized: bool


def inspect_unit(state: State) -> dict[str, Any]:
    """Initial physical and fluid inspection of the generator."""
    inp = state.get("input") or {}
    # Simulate reading sensor data or input specifications
    requested_kva = float(inp.get("target_kva", 750.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_unit"],
        "power_rating_kva": requested_kva,
        "fuel_pressure_psi": 45.5,
        "is_synchronized": False,
    }


def perform_load_test(state: State) -> dict[str, Any]:
    """Applies electrical load and monitors stability and thermals."""
    # Logic simulates engine governor response and thermal rise
    freq = 60.0 if state.get("fuel_pressure_psi", 0) > 40.0 else 58.2
    temp = 82.4 if state.get("power_rating_kva", 0) > 500.0 else 65.0
    return {
        "log": [f"{UNISPSC_CODE}:perform_load_test"],
        "governor_frequency_hz": freq,
        "alternator_winding_temp_c": temp,
        "is_synchronized": freq == 60.0,
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    """Finalizes the operational report and dispatches status."""
    synced = state.get("is_synchronized", False)
    freq = state.get("governor_frequency_hz", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "READY_FOR_GRID" if synced else "FAULT_STABILITY",
            "metrics": {
                "hz": freq,
                "kva": state.get("power_rating_kva"),
                "temp_c": state.get("alternator_winding_temp_c"),
            },
            "certified": synced and freq == 60.0,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_unit)
_g.add_node("test", perform_load_test)
_g.add_node("report", generate_telemetry)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "test")
_g.add_edge("test", "report")
_g.add_edge("report", END)

graph = _g.compile()
