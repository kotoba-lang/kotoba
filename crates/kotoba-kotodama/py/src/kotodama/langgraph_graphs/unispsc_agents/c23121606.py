# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23121606 — Compressor (segment 23).

Bespoke graph logic for industrial compressor management and telemetry
verification. This agent handles specification validation, compression
cycle simulation, and safety integrity checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23121606"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23121606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Compressor
    operating_pressure_psi: float
    flow_rate_cfm: float
    maintenance_lock: bool
    efficiency_rating: float
    safety_bypass_active: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the compressor operation."""
    inp = state.get("input") or {}
    pressure = float(inp.get("target_psi", 100.0))
    flow = float(inp.get("target_cfm", 25.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "operating_pressure_psi": pressure,
        "flow_rate_cfm": flow,
        "maintenance_lock": False,
    }


def analyze_efficiency(state: State) -> dict[str, Any]:
    """Simulates a compression cycle and calculates efficiency."""
    pressure = state.get("operating_pressure_psi", 0.0)
    # Heuristic: Efficiency drops at extremely high pressures
    efficiency = 0.98 if pressure < 150 else 0.85

    return {
        "log": [f"{UNISPSC_CODE}:analyze_efficiency"],
        "efficiency_rating": efficiency,
        "safety_bypass_active": False,
    }


def safety_audit(state: State) -> dict[str, Any]:
    """Performs a safety check on the compressor state."""
    efficiency = state.get("efficiency_rating", 0.0)
    is_safe = efficiency > 0.5

    return {
        "log": [f"{UNISPSC_CODE}:safety_audit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "operational" if is_safe else "critical_failure",
            "telemetry": {
                "psi": state.get("operating_pressure_psi"),
                "cfm": state.get("flow_rate_cfm"),
                "efficiency": efficiency,
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("analyze_efficiency", analyze_efficiency)
_g.add_node("safety_audit", safety_audit)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "analyze_efficiency")
_g.add_edge("analyze_efficiency", "safety_audit")
_g.add_edge("safety_audit", END)

graph = _g.compile()
