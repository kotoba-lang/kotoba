# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26110000 — Power (segment 26).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26110000"
UNISPSC_TITLE = "Power"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26110000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    grid_load_mw: float
    generation_capacity_mw: float
    voltage_kv: float
    frequency_hz: float
    is_balanced: bool


def ingest_telemetry(state: State) -> dict[str, Any]:
    """Reads grid telemetry from input or defaults to nominal values."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:ingest_telemetry"],
        "grid_load_mw": float(inp.get("load", 1200.0)),
        "generation_capacity_mw": float(inp.get("capacity", 1500.0)),
        "voltage_kv": float(inp.get("voltage", 220.0)),
        "frequency_hz": float(inp.get("frequency", 60.0)),
    }


def balance_check(state: State) -> dict[str, Any]:
    """Evaluates if generation matches load within safe frequency bounds."""
    load = state.get("grid_load_mw", 0.0)
    capacity = state.get("generation_capacity_mw", 0.0)
    freq = state.get("frequency_hz", 60.0)

    # Grid is balanced if capacity covers load and frequency is within +/- 0.5Hz
    balanced = (capacity >= load) and (59.5 <= freq <= 60.5)
    return {
        "log": [f"{UNISPSC_CODE}:balance_check: balanced={balanced}"],
        "is_balanced": balanced,
    }


def dispatch_control(state: State) -> dict[str, Any]:
    """Finalizes power dispatch status based on grid stability analysis."""
    balanced = state.get("is_balanced", False)
    status = "NOMINAL_OPERATION" if balanced else "GRID_STRESS_DETECTED"

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_control: status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "load_mw": state.get("grid_load_mw"),
                "generation_mw": state.get("generation_capacity_mw"),
                "voltage_kv": state.get("voltage_kv"),
                "frequency_hz": state.get("frequency_hz"),
            },
            "dispatch_status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_telemetry)
_g.add_node("check", balance_check)
_g.add_node("dispatch", dispatch_control)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "check")
_g.add_edge("check", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
