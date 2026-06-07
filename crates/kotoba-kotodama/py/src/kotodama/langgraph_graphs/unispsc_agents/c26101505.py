# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101505 — Steam Engine.
Bespoke logic for monitoring and simulating steam engine operational states.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101505"
UNISPSC_TITLE = "Steam Engine"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    boiler_pressure_psi: float
    engine_rpm: int
    water_level_percent: float
    is_safe: bool


def inspect_engine(state: State) -> dict[str, Any]:
    """Initial inspection of the steam engine parameters."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 120.0))
    water = float(inp.get("water", 85.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_engine"],
        "boiler_pressure_psi": pressure,
        "water_level_percent": water,
        "is_safe": (pressure < 250.0 and water > 20.0),
    }


def simulate_cycle(state: State) -> dict[str, Any]:
    """Simulates a single power stroke cycle based on pressure."""
    pressure = state.get("boiler_pressure_psi", 0.0)
    is_safe = state.get("is_safe", False)

    rpm = int(pressure * 0.8) if is_safe else 0

    return {
        "log": [f"{UNISPSC_CODE}:simulate_cycle (rpm={rpm})"],
        "engine_rpm": rpm,
    }


def report_status(state: State) -> dict[str, Any]:
    """Finalizes the engine status report."""
    is_safe = state.get("is_safe", False)
    rpm = state.get("engine_rpm", 0)

    status_msg = "Operational" if (is_safe and rpm > 0) else "Idle/Shutdown"

    return {
        "log": [f"{UNISPSC_CODE}:report_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "engine_status": status_msg,
            "rpm": rpm,
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_engine)
_g.add_node("simulate", simulate_cycle)
_g.add_node("report", report_status)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "simulate")
_g.add_edge("simulate", "report")
_g.add_edge("report", END)

graph = _g.compile()
