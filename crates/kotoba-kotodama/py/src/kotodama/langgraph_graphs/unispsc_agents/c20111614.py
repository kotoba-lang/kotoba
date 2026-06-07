# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20111614 — Hydraulic (segment 20).

Bespoke graph logic for hydraulic system monitoring and control.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20111614"
UNISPSC_TITLE = "Hydraulic"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20111614"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    pressure_psi: float
    fluid_temp_c: float
    flow_rate_lpm: float
    safety_lock_engaged: bool


def validate_parameters(state: State) -> dict[str, Any]:
    """Inspect hydraulic parameters for operational safety."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure_psi", 0.0))
    temp = float(inp.get("fluid_temp_c", 0.0))

    log_entry = f"{UNISPSC_CODE}:validate_parameters(P={pressure}, T={temp})"

    # Safety threshold: pressure should not exceed 3000 PSI, temp below 85C
    safety_lock = pressure > 3000.0 or temp > 85.0

    return {
        "log": [log_entry],
        "pressure_psi": pressure,
        "fluid_temp_c": temp,
        "safety_lock_engaged": safety_lock,
    }


def compute_flow(state: State) -> dict[str, Any]:
    """Calculate flow rate based on pressure and safety status."""
    if state.get("safety_lock_engaged"):
        return {
            "log": [f"{UNISPSC_CODE}:compute_flow_safety_lock_active"],
            "flow_rate_lpm": 0.0,
        }

    pressure = state.get("pressure_psi", 0.0)
    # Basic flow approximation: Q = 0.5 * sqrt(P)
    flow_rate = 0.5 * (pressure ** 0.5) if pressure > 0 else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:compute_flow_rate={flow_rate:.2f}"],
        "flow_rate_lpm": flow_rate,
    }


def emit_telemetry(state: State) -> dict[str, Any]:
    """Finalize and emit hydraulic system telemetry."""
    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "data": {
            "pressure_psi": state.get("pressure_psi"),
            "fluid_temp_c": state.get("fluid_temp_c"),
            "flow_rate_lpm": state.get("flow_rate_lpm"),
            "safety_engaged": state.get("safety_lock_engaged"),
        },
        "status": "CRITICAL" if state.get("safety_lock_engaged") else "OK",
    }
    return {
        "log": [f"{UNISPSC_CODE}:emit_telemetry"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("compute", compute_flow)
_g.add_node("emit", emit_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
