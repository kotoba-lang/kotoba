# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172802 — Hydraulic (segment 25).

Bespoke LangGraph implementation for hydraulic system state management and
operational validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172802"
UNISPSC_TITLE = "Hydraulic"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172802"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Hydraulic domain fields
    system_pressure_psi: float
    fluid_viscosity_vg: int
    thermal_load_c: float
    seal_integrity_verified: bool


def monitor_pressure(state: State) -> dict[str, Any]:
    """Node that validates incoming hydraulic pressure against safety limits."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 0.0))

    # Safety threshold for generic hydraulic components in this simulation
    safe = 0.0 <= pressure <= 3000.0

    return {
        "log": [f"{UNISPSC_CODE}:monitor_pressure"],
        "system_pressure_psi": pressure,
        "seal_integrity_verified": safe
    }


def evaluate_fluid_state(state: State) -> dict[str, Any]:
    """Calculates viscosity degradation based on thermal load."""
    inp = state.get("input") or {}
    temp = float(inp.get("temperature", 40.0))
    base_vg = int(inp.get("viscosity_index", 46))

    # Mock degradation logic: viscosity drops if temperature exceeds threshold
    degraded_vg = base_vg if temp < 65 else int(base_vg * 0.75)

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_fluid_state"],
        "thermal_load_c": temp,
        "fluid_viscosity_vg": degraded_vg
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    """Aggregates system state into a final diagnostic result."""
    safe = state.get("seal_integrity_verified", False)
    pressure = state.get("system_pressure_psi", 0.0)
    vg = state.get("fluid_viscosity_vg", 0)

    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "pressure_psi": pressure,
                "viscosity_vg": vg,
                "status": "NOMINAL" if safe else "CRITICAL"
            },
            "ok": safe
        }
    }


_g = StateGraph(State)
_g.add_node("monitor", monitor_pressure)
_g.add_node("evaluate", evaluate_fluid_state)
_g.add_node("telemetry", generate_telemetry)

_g.add_edge(START, "monitor")
_g.add_edge("monitor", "evaluate")
_g.add_edge("evaluate", "telemetry")
_g.add_edge("telemetry", END)

graph = _g.compile()
