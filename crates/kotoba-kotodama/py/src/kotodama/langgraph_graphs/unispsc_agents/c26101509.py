# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101509 — Hydro Node.
Bespoke logic for managing hydroelectric generation state and telemetry.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101509"
UNISPSC_TITLE = "Hydro Node"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Hydroelectric operations
    head_pressure_pa: float
    flow_rate_m3s: float
    efficiency: float
    power_output_mw: float


def telemetry(state: State) -> dict[str, Any]:
    """Validate sensor telemetry and initialize hydro parameters."""
    inp = state.get("input") or {}
    # Extract hydraulic parameters from input or use nominal defaults
    pressure = float(inp.get("pressure", 980000.0))
    flow = float(inp.get("flow", 50.0))

    return {
        "log": [f"{UNISPSC_CODE}:telemetry_received: pressure={pressure}Pa, flow={flow}m3/s"],
        "head_pressure_pa": pressure,
        "flow_rate_m3s": flow,
        "efficiency": 0.92,
    }


def compute_generation(state: State) -> dict[str, Any]:
    """Calculate power output based on hydraulic head and flow."""
    pressure = state.get("head_pressure_pa", 0.0)
    flow = state.get("flow_rate_m3s", 0.0)
    efficiency = state.get("efficiency", 0.0)

    # Power (W) = Pressure (Pa) * Flow (m3/s) * Efficiency
    power_w = pressure * flow * efficiency
    power_mw = round(power_w / 1_000_000.0, 3)

    return {
        "log": [f"{UNISPSC_CODE}:generation_computed: {power_mw}MW"],
        "power_output_mw": power_mw,
    }


def finalize(state: State) -> dict[str, Any]:
    """Synchronize with grid and emit final state."""
    power = state.get("power_output_mw", 0.0)
    status = "online" if power > 0 else "idle"

    return {
        "log": [f"{UNISPSC_CODE}:grid_synchronized: status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "generation": {
                "active_power_mw": power,
                "unit": "MW",
                "status": status
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("telemetry", telemetry)
_g.add_node("compute_generation", compute_generation)
_g.add_node("finalize", finalize)

_g.add_edge(START, "telemetry")
_g.add_edge("telemetry", "compute_generation")
_g.add_edge("compute_generation", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
