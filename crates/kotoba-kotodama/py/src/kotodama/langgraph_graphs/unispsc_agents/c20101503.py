# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20101503 — Power Transmission (segment 20).

Bespoke LangGraph implementation for monitoring and optimizing high-voltage
power transmission grids.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101503"
UNISPSC_TITLE = "Power Transmission"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Power Transmission
    line_voltage_kv: float
    current_load_mw: float
    transmission_loss_pct: float
    grid_stability_index: float
    thermal_rating_margin: float


def inspect_substation(state: State) -> dict[str, Any]:
    """Initial node to parse telemetry and establish baseline grid state."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage_kv", 500.0))
    load = float(inp.get("load_mw", 1200.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_substation: {voltage}kV line detected"],
        "line_voltage_kv": voltage,
        "current_load_mw": load,
        "grid_stability_index": 0.98 if load < 2000 else 0.85,
    }


def calculate_transmission_efficiency(state: State) -> dict[str, Any]:
    """Calculates losses based on voltage and current load physics."""
    v = state.get("line_voltage_kv", 1.0)
    l = state.get("current_load_mw", 0.0)

    # Simple model: higher voltage reduces proportional ohmic losses
    loss = (l / (v * 10)) * 2.5
    margin = 100.0 - (l / 50.0)  # Simple thermal limit proxy

    return {
        "log": [f"{UNISPSC_CODE}:calculate_efficiency: loss calculated at {loss:.2f}%"],
        "transmission_loss_pct": round(loss, 3),
        "thermal_rating_margin": round(margin, 2),
    }


def finalize_load_dispatch(state: State) -> dict[str, Any]:
    """Emits the final transmission report and readiness status."""
    stability = state.get("grid_stability_index", 0.0)
    margin = state.get("thermal_rating_margin", 0.0)

    is_safe = stability > 0.8 and margin > 10.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_load_dispatch: safety_check={'PASS' if is_safe else 'FAIL'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "loss_pct": state.get("transmission_loss_pct"),
                "stability": stability,
                "margin": margin
            },
            "dispatch_authorized": is_safe,
            "status": "OPERATIONAL" if is_safe else "LOAD_SHEDDING_REQUIRED"
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_substation)
_g.add_node("calculate", calculate_transmission_efficiency)
_g.add_node("finalize", finalize_load_dispatch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
