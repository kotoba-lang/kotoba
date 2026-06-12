# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23161605 — Machine (segment 23).
Bespoke graph logic for industrial machinery processing and state management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23161605"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23161605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for "Machine"
    machine_id: str
    operational_hours: float
    maintenance_threshold: float
    safety_interlock_active: bool
    current_load_metric: float


def initialize_machine_state(state: State) -> dict[str, Any]:
    """Initializes the machine parameters from the input context."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:initialize_machine_state"],
        "machine_id": inp.get("id", "MCH-DEFAULT-001"),
        "operational_hours": inp.get("hours", 0.0),
        "maintenance_threshold": 5000.0,
        "safety_interlock_active": True,
        "current_load_metric": 0.0,
    }


def perform_diagnostic_check(state: State) -> dict[str, Any]:
    """Checks operational hours against maintenance thresholds and safety status."""
    hours = state.get("operational_hours", 0.0)
    threshold = state.get("maintenance_threshold", 5000.0)
    safety_ok = state.get("safety_interlock_active", False)

    diagnostic_passed = safety_ok and (hours < threshold)

    return {
        "log": [f"{UNISPSC_CODE}:perform_diagnostic_check:passed={diagnostic_passed}"],
        "current_load_metric": 10.5 if diagnostic_passed else 0.0,
    }


def execute_processing_cycle(state: State) -> dict[str, Any]:
    """Simulates a machine cycle if diagnostics and safety are cleared."""
    load = state.get("current_load_metric", 0.0)
    hours = state.get("operational_hours", 0.0)

    # Increment operational hours by a nominal cycle time
    new_hours = hours + 0.25 if load > 0 else hours

    return {
        "log": [f"{UNISPSC_CODE}:execute_processing_cycle:load={load}"],
        "operational_hours": new_hours,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Produces the final result object containing machine telemetry."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "machine_id": state.get("machine_id"),
                "total_hours": state.get("operational_hours"),
                "load": state.get("current_load_metric"),
                "safety_lock": state.get("safety_interlock_active"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_machine_state)
_g.add_node("diagnostic", perform_diagnostic_check)
_g.add_node("process", execute_processing_cycle)
_g.add_node("emit", finalize_telemetry)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "diagnostic")
_g.add_edge("diagnostic", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
