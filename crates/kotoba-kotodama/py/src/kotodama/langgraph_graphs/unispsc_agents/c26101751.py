# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101751 — Engine Control (segment 26).

Bespoke graph for monitoring and controlling internal combustion engine
parameters, focusing on sensor ingestion, fuel optimization, and
safety diagnostics.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101751"
UNISPSC_TITLE = "Engine Control"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101751"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Engine Control
    engine_rpm: int
    coolant_temp_c: float
    throttle_pct: float
    fuel_trim: float
    active_faults: list[str]


def monitor_sensors(state: State) -> dict[str, Any]:
    """Reads raw sensor data from input and initializes state."""
    inp = state.get("input") or {}
    rpm = inp.get("rpm", 0)
    temp = inp.get("temp", 90.0)
    throttle = inp.get("throttle", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:monitor_sensors(rpm={rpm}, temp={temp})"],
        "engine_rpm": rpm,
        "coolant_temp_c": temp,
        "throttle_pct": throttle,
        "active_faults": [],
    }


def compute_control_parameters(state: State) -> dict[str, Any]:
    """Calculates fuel trim and ignition adjustments based on engine state."""
    rpm = state.get("engine_rpm", 0)
    temp = state.get("coolant_temp_c", 0.0)

    # Simple logic: rich mixture if cold, lean if warm/high RPM
    trim = 1.0
    if temp < 70:
        trim = 1.15  # Rich
    elif rpm > 5000:
        trim = 1.05  # Power enrichment

    return {
        "log": [f"{UNISPSC_CODE}:compute_control(trim={trim:.2f})"],
        "fuel_trim": trim,
    }


def safety_interlock(state: State) -> dict[str, Any]:
    """Validates parameters against safety thresholds."""
    temp = state.get("coolant_temp_c", 0.0)
    rpm = state.get("engine_rpm", 0)
    faults = []

    if temp > 110:
        faults.append("OVERHEAT_WARNING")
    if rpm > 7000:
        faults.append("REDLINE_EXCEEDED")

    return {
        "log": [f"{UNISPSC_CODE}:safety_interlock(faults={len(faults)})"],
        "active_faults": faults,
    }


def emit_telemetry(state: State) -> dict[str, Any]:
    """Constructs the final execution result."""
    faults = state.get("active_faults", [])
    status = "NOMINAL" if not faults else "DEGRADED"

    return {
        "log": [f"{UNISPSC_CODE}:emit_telemetry(status={status})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "engine_status": status,
            "fault_codes": faults,
            "control_data": {
                "fuel_trim": state.get("fuel_trim"),
                "rpm": state.get("engine_rpm"),
            },
            "ok": len(faults) == 0,
        },
    }


_g = StateGraph(State)
_g.add_node("monitor", monitor_sensors)
_g.add_node("optimize", compute_control_parameters)
_g.add_node("safety", safety_interlock)
_g.add_node("emit", emit_telemetry)

_g.add_edge(START, "monitor")
_g.add_edge("monitor", "optimize")
_g.add_edge("optimize", "safety")
_g.add_edge("safety", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
