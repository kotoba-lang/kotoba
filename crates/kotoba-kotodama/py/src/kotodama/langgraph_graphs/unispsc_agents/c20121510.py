# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121510 — Machine (segment 20).

Bespoke graph logic for industrial drilling machinery operation and monitoring.
This agent validates safety protocols, simulates workload execution, and
reports performance metrics including efficiency and maintenance needs.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121510"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    operational_mode: str
    safety_protocol_active: bool
    maintenance_required: bool
    performance_metrics: dict[str, Any]


def validate_safety(state: State) -> dict[str, Any]:
    """Validate machine safety locks and operational readiness."""
    inp = state.get("input") or {}
    # Machine operation is prohibited if an emergency stop signal is present
    is_safe = not inp.get("emergency_stop", False)
    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "safety_protocol_active": is_safe,
        "operational_mode": "ready" if is_safe else "fault",
    }


def process_workload(state: State) -> dict[str, Any]:
    """Execute the machine's primary function based on the input load."""
    if state.get("operational_mode") == "fault":
        return {
            "log": [f"{UNISPSC_CODE}:process_workload_bypassed"],
            "maintenance_required": True,
        }

    inp = state.get("input") or {}
    current_load = inp.get("load", 50)

    # Calculate machine efficiency and detect strain-based maintenance needs
    efficiency = 0.95 if current_load < 100 else 0.72
    needs_maint = current_load > 150

    return {
        "log": [f"{UNISPSC_CODE}:process_workload"],
        "operational_mode": "running",
        "performance_metrics": {
            "efficiency_ratio": efficiency,
            "load_processed": current_load,
            "core_temperature_c": 40 + (current_load * 0.4),
        },
        "maintenance_required": needs_maint,
    }


def emit_status(state: State) -> dict[str, Any]:
    """Emit the final machine status and operational metrics."""
    mode = state.get("operational_mode", "unknown")
    metrics = state.get("performance_metrics", {})
    maint = state.get("maintenance_required", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational_status": mode,
            "metrics": metrics,
            "maintenance_alert": maint,
            "ok": mode != "fault",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_safety", validate_safety)
_g.add_node("process_workload", process_workload)
_g.add_node("emit_status", emit_status)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "process_workload")
_g.add_edge("process_workload", "emit_status")
_g.add_edge("emit_status", END)

graph = _g.compile()
