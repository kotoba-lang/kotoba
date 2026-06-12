# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201509 — Aileron (segment 25).

Bespoke logic for flight control surface monitoring and actuation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201509"
UNISPSC_TITLE = "Aileron"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Aileron control
    deflection_degrees: float
    hinge_moment_nm: float
    servo_current_ma: float
    structural_health: float


def preflight_check(state: State) -> dict[str, Any]:
    """Node: Verify structural integrity and initial sensor data."""
    inp = state.get("input") or {}
    health = float(inp.get("health", 1.0))
    return {
        "log": [f"{UNISPSC_CODE}:preflight_check"],
        "structural_health": health,
        "servo_current_ma": 450.0 if health > 0.9 else 0.0,
    }


def compute_actuation(state: State) -> dict[str, Any]:
    """Node: Determine required deflection based on roll demand."""
    inp = state.get("input") or {}
    roll_demand = float(inp.get("roll_demand", 0.0))

    # Simple linear mapping for aileron deflection (-25 to +25 degrees)
    target_deflection = roll_demand * 25.0
    # Simulated hinge moment resistance (Newton-meters)
    resistance = abs(target_deflection) * 1.5

    return {
        "log": [f"{UNISPSC_CODE}:compute_actuation"],
        "deflection_degrees": max(-25.0, min(25.0, target_deflection)),
        "hinge_moment_nm": resistance,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Node: Package actuation results and health metrics."""
    health = state.get("structural_health", 0.0)
    current = state.get("servo_current_ma", 0.0)

    # Operational if health is high and electrical subsystem is responsive
    is_operational = health > 0.95 and current > 100.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "deflection": state.get("deflection_degrees"),
                "moment": state.get("hinge_moment_nm"),
                "current": current,
            },
            "status": "active" if is_operational else "fault_detected",
            "ok": is_operational,
        },
    }


_g = StateGraph(State)
_g.add_node("preflight_check", preflight_check)
_g.add_node("compute_actuation", compute_actuation)
_g.add_node("finalize_telemetry", finalize_telemetry)

_g.add_edge(START, "preflight_check")
_g.add_edge("preflight_check", "compute_actuation")
_g.add_edge("compute_actuation", "finalize_telemetry")
_g.add_edge("finalize_telemetry", END)

graph = _g.compile()
