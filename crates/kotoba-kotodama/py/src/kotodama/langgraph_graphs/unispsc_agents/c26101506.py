# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101506 — Turbine (segment 26).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101506"
UNISPSC_TITLE = "Turbine"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Turbine domain state
    rpm_actual: float
    inlet_temp_k: float
    exhaust_temp_k: float
    vibration_mm_s: float
    efficiency_pct: float


def validate_telemetry(state: State) -> dict[str, Any]:
    """Validates incoming turbine sensor data."""
    inp = state.get("input") or {}
    rpm = float(inp.get("rpm", 3000.0))
    inlet = float(inp.get("inlet_temp", 1200.0))
    exhaust = float(inp.get("exhaust_temp", 650.0))
    vibration = float(inp.get("vibration", 1.5))

    return {
        "log": [f"{UNISPSC_CODE}:validate_telemetry"],
        "rpm_actual": rpm,
        "inlet_temp_k": inlet,
        "exhaust_temp_k": exhaust,
        "vibration_mm_s": vibration,
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Calculates thermodynamic efficiency and checks safety limits."""
    inlet = state.get("inlet_temp_k", 1200.0)
    exhaust = state.get("exhaust_temp_k", 650.0)
    vibration = state.get("vibration_mm_s", 1.5)

    # Carnot-inspired efficiency estimate
    efficiency = (1.0 - (exhaust / inlet)) * 100.0 if inlet > 0 else 0.0

    log_entry = f"{UNISPSC_CODE}:analyze_performance"
    if vibration > 5.0:
        log_entry += " (HIGH_VIBRATION_WARNING)"

    return {
        "log": [log_entry],
        "efficiency_pct": round(efficiency, 2),
    }


def emit_report(state: State) -> dict[str, Any]:
    """Formats the final diagnostic output for the turbine."""
    eff = state.get("efficiency_pct", 0.0)
    rpm = state.get("rpm_actual", 0.0)
    vib = state.get("vibration_mm_s", 0.0)

    status = "OPERATIONAL"
    if vib > 4.0 or eff < 30.0:
        status = "MAINTENANCE_REQUIRED"
    if rpm > 4500.0:
        status = "OVERSPEED_ALARM"

    return {
        "log": [f"{UNISPSC_CODE}:emit_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": status,
            "efficiency": f"{eff}%",
            "ok": status == "OPERATIONAL",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_telemetry)
_g.add_node("analyze", analyze_performance)
_g.add_node("report", emit_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "report")
_g.add_edge("report", END)

graph = _g.compile()
