# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26000000 — Power System (segment 26).

Bespoke graph logic for monitoring and managing power system operations.
This module defines a state machine for evaluating grid stability, load balancing,
and final distribution reporting within the Power System domain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26000000"
UNISPSC_TITLE = "Power System"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26000000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    voltage_v: float
    load_kw: float
    frequency_hz: float
    grid_status: str


def monitor_voltage(state: State) -> dict[str, Any]:
    """Simulates real-time voltage monitoring of the power system."""
    inp = state.get("input") or {}
    v = inp.get("voltage", 230.0)
    status = "nominal" if 210 <= v <= 250 else "alert"
    return {
        "log": [f"{UNISPSC_CODE}:monitor_voltage - detected {v}V"],
        "voltage_v": v,
        "grid_status": status,
    }


def calculate_load(state: State) -> dict[str, Any]:
    """Calculates the current system load and frequency stability."""
    inp = state.get("input") or {}
    l_kw = inp.get("load", 50.5)
    f_hz = inp.get("frequency", 60.0)
    return {
        "log": [f"{UNISPSC_CODE}:calculate_load - processing {l_kw}kW"],
        "load_kw": l_kw,
        "frequency_hz": f_hz,
    }


def finalize_grid_state(state: State) -> dict[str, Any]:
    """Consolidates system metrics into the final power system report."""
    metrics = {
        "voltage": state.get("voltage_v"),
        "load": state.get("load_kw"),
        "frequency": state.get("frequency_hz"),
        "status": state.get("grid_status"),
    }
    return {
        "log": [f"{UNISPSC_CODE}:finalize_grid_state - reporting metrics"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": metrics,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("monitor_voltage", monitor_voltage)
_g.add_node("calculate_load", calculate_load)
_g.add_node("finalize_grid_state", finalize_grid_state)

_g.add_edge(START, "monitor_voltage")
_g.add_edge("monitor_voltage", "calculate_load")
_g.add_edge("calculate_load", "finalize_grid_state")
_g.add_edge("finalize_grid_state", END)

graph = _g.compile()
