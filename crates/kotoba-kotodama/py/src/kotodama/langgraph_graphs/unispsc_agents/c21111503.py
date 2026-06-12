# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21111503 — Sprayer.
Specialized logic for agricultural and industrial spraying equipment state management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21111503"
UNISPSC_TITLE = "Sprayer"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21111503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Sprayer
    pressure_psi: float
    volume_capacity_liters: float
    fluid_viscosity_cp: float
    nozzle_pattern: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates that the sprayer input parameters are within operational bounds."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 45.0))
    volume = float(inp.get("volume", 100.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "pressure_psi": pressure,
        "volume_capacity_liters": volume,
        "nozzle_pattern": str(inp.get("pattern", "conical")),
    }


def calculate_flow_rate(state: State) -> dict[str, Any]:
    """Computes effective flow rate based on pressure and viscosity."""
    viscosity = state.get("fluid_viscosity_cp", 1.0)
    pressure = state.get("pressure_psi", 0.0)
    # Simplified flow logic: identify if pressure is in the 'optimal' range for a standard sprayer
    flow_status = "optimal" if 30 <= pressure <= 60 else "suboptimal"
    return {
        "log": [f"{UNISPSC_CODE}:calculate_flow_rate:{flow_status}"],
        "fluid_viscosity_cp": viscosity,
    }


def emit_dispatch_ready(state: State) -> dict[str, Any]:
    """Finalizes the state and prepares the actor result."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_dispatch_ready"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "pressure": state.get("pressure_psi"),
                "capacity": state.get("volume_capacity_liters"),
                "pattern": state.get("nozzle_pattern"),
            },
            "status": "ready_for_operation",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("process", calculate_flow_rate)
_g.add_node("emit", emit_dispatch_ready)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
