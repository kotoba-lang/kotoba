# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23121611 — Compressor.
Bespoke logic for industrial compressor simulation and reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23121611"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23121611"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for a Compressor
    target_pressure_psi: float
    measured_flow_cfm: float
    compression_ratio: float
    maintenance_lockout: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the input parameters for compressor operation."""
    inp = state.get("input") or {}
    psi = float(inp.get("target_pressure", 90.0))
    ratio = psi / 14.7  # Approximation of compression ratio at sea level

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "target_pressure_psi": psi,
        "compression_ratio": ratio,
        "maintenance_lockout": inp.get("maintenance_mode", False),
    }


def compute_output(state: State) -> dict[str, Any]:
    """Computes output flow based on pressure and state."""
    if state.get("maintenance_lockout"):
        return {
            "log": [f"{UNISPSC_CODE}:compute_output:lockout"],
            "measured_flow_cfm": 0.0,
        }

    psi = state.get("target_pressure_psi", 0.0)
    # Simple model: flow decreases as pressure increases
    flow = max(0.0, 500.0 - (psi * 2.0))

    return {
        "log": [f"{UNISPSC_CODE}:compute_output"],
        "measured_flow_cfm": flow,
    }


def emit_telemetry(state: State) -> dict[str, Any]:
    """Generates the final telemetry report for the compressor."""
    is_locked = state.get("maintenance_lockout", False)
    flow = state.get("measured_flow_cfm", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:emit_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "MAINTENANCE" if is_locked else "ACTIVE",
            "telemetry": {
                "pressure_psi": state.get("target_pressure_psi"),
                "flow_cfm": flow,
                "compression_ratio": round(state.get("compression_ratio", 0.0), 2),
            },
            "ok": not is_locked,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("compute", compute_output)
_g.add_node("emit", emit_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
