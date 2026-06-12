# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111007 — Blast (segment 13).

Bespoke graph logic for industrial blasting materials and processes.
This agent manages the state transitions for blast parameter calculation,
safety verification, and yield simulation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111007"
UNISPSC_TITLE = "Blast"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111007"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Blast
    charge_weight: float
    detonation_velocity: float
    fragmentation_index: float
    safety_clearance: bool
    pressure_peak: float


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates the blast configuration and sets initial metrics."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))
    velocity = float(inp.get("velocity", 5000.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters -> weight={weight}"],
        "charge_weight": weight,
        "detonation_velocity": velocity,
        "safety_clearance": weight < 1000.0,  # Logic: threshold for auto-clearance
    }


def compute_dynamics(state: State) -> dict[str, Any]:
    """Calculates the physical dynamics of the blast based on charge and velocity."""
    weight = state.get("charge_weight", 0.0)
    velocity = state.get("detonation_velocity", 0.0)

    # Simple simulation logic for pressure and fragmentation
    peak = weight * (velocity / 1000.0) * 1.5
    frag = (velocity / weight) if weight > 0 else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:compute_dynamics -> peak_pressure={peak:.2f}"],
        "pressure_peak": peak,
        "fragmentation_index": frag,
    }


def synthesize_report(state: State) -> dict[str, Any]:
    """Finalizes the blast state and generates the actor result."""
    safe = state.get("safety_clearance", False)
    peak = state.get("pressure_peak", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:synthesize_report -> safe={safe}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "peak_pressure_kpa": peak,
                "fragmentation": state.get("fragmentation_index", 0.0),
                "safety_status": "APPROVED" if safe else "REJECTED",
            },
            "status": "success" if safe else "warning",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_parameters)
_g.add_node("compute", compute_dynamics)
_g.add_node("report", synthesize_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "report")
_g.add_edge("report", END)

graph = _g.compile()
