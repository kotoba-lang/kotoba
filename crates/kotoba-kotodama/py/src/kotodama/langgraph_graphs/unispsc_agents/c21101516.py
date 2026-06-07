# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101516"
UNISPSC_TITLE = "Excavator"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101516"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Excavator heavy equipment
    hydraulic_pressure_psi: float
    safety_interlock_active: bool
    bucket_capacity_m3: float
    operating_hours: float


def inspect_safety(state: State) -> dict[str, Any]:
    """Perform a pre-operation safety check and system diagnostic."""
    inp = state.get("input") or {}
    # Simulate reading sensor data or input parameters
    pressure = float(inp.get("pressure_psi", 2800.0))
    interlock = bool(inp.get("safety_lock", True))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_safety"],
        "hydraulic_pressure_psi": pressure,
        "safety_interlock_active": interlock,
    }


def log_telemetry(state: State) -> dict[str, Any]:
    """Calculate bucket metrics and update equipment operating hours."""
    inp = state.get("input") or {}
    prev_hours = float(inp.get("prev_hours", 1240.5))
    capacity = float(inp.get("capacity_m3", 1.5))

    return {
        "log": [f"{UNISPSC_CODE}:log_telemetry"],
        "bucket_capacity_m3": capacity,
        "operating_hours": prev_hours + 0.1,  # Simulate incrementing operation time
    }


def generate_status(state: State) -> dict[str, Any]:
    """Compile the final operational report for the excavator agent."""
    is_safe = state.get("safety_interlock_active", False)
    pressure = state.get("hydraulic_pressure_psi", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:generate_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "OPERATIONAL" if (is_safe and 2000 < pressure < 3500) else "MAINTENANCE_REQUIRED",
            "telemetry": {
                "pressure_psi": pressure,
                "hours": state.get("operating_hours"),
                "bucket_m3": state.get("bucket_capacity_m3"),
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_safety)
_g.add_node("telemetry", log_telemetry)
_g.add_node("status", generate_status)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "telemetry")
_g.add_edge("telemetry", "status")
_g.add_edge("status", END)

graph = _g.compile()
