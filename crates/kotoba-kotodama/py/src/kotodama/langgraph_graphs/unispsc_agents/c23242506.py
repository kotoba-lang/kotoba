# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242506 — Machine (segment 23).

Bespoke graph logic for industrial machine monitoring and status reporting.
This agent handles machine-specific state transitions including safety
verification and workload analysis for manufacturing machinery.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242506"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Machine-specific domain fields
    machine_id: str
    safety_protocol_met: bool
    workload_efficiency: float
    maintenance_alert: bool


def validate_machine_safety(state: State) -> dict[str, Any]:
    """Inspects machine configuration and ensures safety protocols are active."""
    inp = state.get("input") or {}
    m_id = inp.get("machine_id", "MCH-DEFAULT-001")
    safety_check = inp.get("safety_sensor_active", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_machine_safety"],
        "machine_id": m_id,
        "safety_protocol_met": safety_check,
    }


def analyze_workload_capacity(state: State) -> dict[str, Any]:
    """Calculates operational efficiency based on provided input parameters."""
    inp = state.get("input") or {}
    requested_load = inp.get("load_units", 0)

    # Simple logic: higher load without safety protocols triggers maintenance alerts
    efficiency = min(1.0, 100 / requested_load) if requested_load > 0 else 0.0
    alert = requested_load > 150 or not state.get("safety_protocol_met")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_workload_capacity"],
        "workload_efficiency": efficiency,
        "maintenance_alert": alert,
    }


def emit_machine_telemetry(state: State) -> dict[str, Any]:
    """Compiles the final state into a machine telemetry report."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_machine_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "machine_id": state.get("machine_id"),
            "status": "OPERATIONAL" if not state.get("maintenance_alert") else "WARNING",
            "efficiency": state.get("workload_efficiency"),
            "safety_verified": state.get("safety_protocol_met"),
            "ok": state.get("safety_protocol_met") and not state.get("maintenance_alert"),
        },
    }


_g = StateGraph(State)

_g.add_node("validate_safety", validate_machine_safety)
_g.add_node("analyze_workload", analyze_workload_capacity)
_g.add_node("emit_telemetry", emit_machine_telemetry)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "analyze_workload")
_g.add_edge("analyze_workload", "emit_telemetry")
_g.add_edge("emit_telemetry", END)

graph = _g.compile()
