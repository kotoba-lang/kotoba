# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101766 — Governor (segment 26).

Bespoke LangGraph implementation for speed and load regulation of prime movers.
This agent monitors engine telemetry, calculates throttle adjustments, and
enforces overspeed safety limits.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101766"
UNISPSC_TITLE = "Governor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101766"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields
    target_rpm: float
    current_load_pct: float
    actuator_drive: float
    overspeed_fault: bool
    governance_mode: str


def monitor_telemetry(state: State) -> dict[str, Any]:
    """Injest system telemetry and determine the operational set-point."""
    inp = state.get("input") or {}
    rpm = float(inp.get("set_point", 1800.0))
    load = float(inp.get("actual_load", 0.0))
    mode = str(inp.get("mode", "ISOCHRONOUS"))

    return {
        "log": [f"{UNISPSC_CODE}:monitor_telemetry(rpm={rpm}, load={load}%)"],
        "target_rpm": rpm,
        "current_load_pct": load,
        "governance_mode": mode,
    }


def calculate_regulation(state: State) -> dict[str, Any]:
    """Compute PID-like adjustment for the fuel/steam actuator."""
    target = state.get("target_rpm", 1800.0)
    load = state.get("current_load_pct", 0.0)

    # Overspeed protection logic
    fault = target > 2200.0 or load > 110.0

    # Calculate drive signal (simplified proportional logic)
    # Higher load requires more actuator drive to maintain RPM
    drive = min(100.0, max(0.0, load * 0.9))

    if fault:
        drive = 0.0  # Emergency shutdown

    return {
        "log": [f"{UNISPSC_CODE}:calculate_regulation(drive={drive}%, fault={fault})"],
        "actuator_drive": drive,
        "overspeed_fault": fault,
    }


def dispatch_control(state: State) -> dict[str, Any]:
    """Package the regulation output for the hardware interface."""
    is_faulted = state.get("overspeed_fault", False)

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_control"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "actuator_output_ma": 4.0 + (state.get("actuator_drive", 0.0) * 0.16),
            "status": "CRITICAL_FAULT" if is_faulted else "NORMAL",
            "did": UNISPSC_DID,
            "ok": not is_faulted,
        },
    }


_g = StateGraph(State)
_g.add_node("monitor", monitor_telemetry)
_g.add_node("regulate", calculate_regulation)
_g.add_node("dispatch", dispatch_control)

_g.add_edge(START, "monitor")
_g.add_edge("monitor", "regulate")
_g.add_edge("regulate", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
