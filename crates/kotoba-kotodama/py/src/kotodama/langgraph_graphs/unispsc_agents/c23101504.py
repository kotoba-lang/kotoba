# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23101504 — Compressor (segment 23).

Bespoke graph logic for industrial compressor simulation and specification
validation. This agent manages the state transitions for air and gas
compression requirements, calculating efficiency ratings and maintenance
thresholds based on input pressure and flow metrics.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23101504"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23101504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Compressor
    pressure_psi: float
    flow_cfm: float
    maintenance_threshold_exceeded: bool
    compression_efficiency: str
    thermal_load: float


def validate_specifications(state: State) -> dict[str, Any]:
    """Analyzes input data for compressor ratings."""
    inp = state.get("input") or {}
    psi = float(inp.get("pressure", 120.0))
    cfm = float(inp.get("flow", 15.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "pressure_psi": psi,
        "flow_cfm": cfm,
    }


def compute_performance_metrics(state: State) -> dict[str, Any]:
    """Calculates efficiency and thermal load based on PSI and CFM."""
    psi = state.get("pressure_psi", 0.0)
    cfm = state.get("flow_cfm", 0.0)

    # Simple logic: higher pressure increases thermal load and maintenance risk
    efficiency = "Optimal" if psi <= 150 else "Degraded"
    maint_trip = psi > 250 or cfm > 100
    load = (psi * cfm) / 1000.0

    return {
        "log": [f"{UNISPSC_CODE}:compute_performance_metrics"],
        "compression_efficiency": efficiency,
        "maintenance_threshold_exceeded": maint_trip,
        "thermal_load": load,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Generates the final compressor state report."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "pressure_psi": state.get("pressure_psi"),
                "flow_cfm": state.get("flow_cfm"),
                "efficiency": state.get("compression_efficiency"),
                "thermal_load": state.get("thermal_load"),
            },
            "system_status": "ALARM" if state.get("maintenance_threshold_exceeded") else "OK",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("compute", compute_performance_metrics)
_g.add_node("finalize", finalize_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
