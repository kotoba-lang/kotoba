# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101103 — Motor (segment 26).

Bespoke graph logic for electric motor power source modeling, covering
specification validation, load performance simulation, and diagnostic reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101103"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101103"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Motor
    voltage_rating: int
    rpm_actual: float
    thermal_status: str
    load_factor: float
    is_operational: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validate input specifications for the motor unit."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 230)
    is_valid = 110 <= voltage <= 480

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "voltage_rating": voltage,
        "is_operational": is_valid,
        "thermal_status": "nominal" if is_valid else "out_of_range",
    }


def simulate_performance(state: State) -> dict[str, Any]:
    """Calculate performance metrics based on load and voltage."""
    if not state.get("is_operational"):
        return {
            "log": [f"{UNISPSC_CODE}:simulate_performance_skipped"],
            "rpm_actual": 0.0,
            "load_factor": 0.0,
        }

    # Simple simulation logic
    inp = state.get("input") or {}
    requested_load = inp.get("load", 0.5)
    voltage = state.get("voltage_rating", 230)

    # Efficiency decreases as load exceeds 1.0
    rpm = 1800.0 * (voltage / 230.0) * (1.0 - (requested_load * 0.05))

    return {
        "log": [f"{UNISPSC_CODE}:simulate_performance"],
        "rpm_actual": round(rpm, 2),
        "load_factor": float(requested_load),
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Finalize the motor diagnostic and operational report."""
    is_ok = state.get("is_operational", False)
    rpm = state.get("rpm_actual", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "voltage": state.get("voltage_rating"),
                "rpm": rpm,
                "load": state.get("load_factor"),
                "thermal": state.get("thermal_status"),
            },
            "status": "ready" if is_ok and rpm > 0 else "error",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specs)
_g.add_node("simulate", simulate_performance)
_g.add_node("finalize", finalize_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "simulate")
_g.add_edge("simulate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
