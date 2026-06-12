# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121517 — Pipeline.
Bespoke implementation for structural integrity monitoring and flow optimization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121517"
UNISPSC_TITLE = "Pipeline"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121517"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Pipeline infrastructure
    pressure_psi: float
    integrity_check_passed: bool
    flow_throughput: float
    maintenance_alert: bool


def inspect_infrastructure(state: State) -> dict[str, Any]:
    """Inspects the physical pipeline for pressure deviations and integrity."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 120.0))
    # Threshold for structural stress
    integrity = pressure < 180.0
    return {
        "log": [f"{UNISPSC_CODE}:inspect_infrastructure"],
        "pressure_psi": pressure,
        "integrity_check_passed": integrity,
        "maintenance_alert": not integrity,
    }


def analyze_flow_telemetry(state: State) -> dict[str, Any]:
    """Calculates throughput based on pressure and integrity constraints."""
    integrity = state.get("integrity_check_passed", False)
    pressure = state.get("pressure_psi", 0.0)

    # If integrity is compromised, shut down flow for safety
    throughput = (pressure * 1.25) if integrity else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_flow_telemetry"],
        "flow_throughput": throughput,
    }


def emit_status_report(state: State) -> dict[str, Any]:
    """Compiles the final operational status of the pipeline segment."""
    integrity = state.get("integrity_check_passed", False)
    throughput = state.get("flow_throughput", 0.0)
    alert = state.get("maintenance_alert", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_status_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "OPERATIONAL" if integrity and throughput > 0 else "OFFLINE",
            "metrics": {
                "pressure": state.get("pressure_psi"),
                "throughput": throughput,
                "safety_alert": alert,
            },
            "ok": integrity,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_infrastructure)
_g.add_node("analyze", analyze_flow_telemetry)
_g.add_node("emit", emit_status_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
