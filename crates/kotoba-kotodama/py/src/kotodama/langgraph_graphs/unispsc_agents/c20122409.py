# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122409 — Mining and Well Drilling Machinery (segment 20).

This bespoke implementation handles telemetry processing and safety analysis for
drilling operations, replacing the placeholder compliance pipeline.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122409"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122409"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for well drilling
    wellbore_id: str
    drill_bit_wear: float
    coolant_pressure_psi: float
    safety_interlock_active: bool


def intake_telemetry(state: State) -> dict[str, Any]:
    """Extracts drilling parameters from the input payload."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:intake_telemetry"],
        "wellbore_id": str(inp.get("wellbore_id", "WB-UNKNOWN")),
        "drill_bit_wear": float(inp.get("wear_factor", 0.0)),
        "coolant_pressure_psi": float(inp.get("pressure", 1200.0)),
    }


def analyze_safety_thresholds(state: State) -> dict[str, Any]:
    """Evaluates wear and pressure to determine if safety interlocks are required."""
    wear = state.get("drill_bit_wear", 0.0)
    pressure = state.get("coolant_pressure_psi", 0.0)

    # Trigger interlock if wear is critical or pressure is outside nominal range
    interlock = wear > 0.92 or pressure < 400.0 or pressure > 3500.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_safety_thresholds"],
        "safety_interlock_active": interlock,
    }


def finalize_drilling_state(state: State) -> dict[str, Any]:
    """Compiles the final operational report for the drilling machinery."""
    is_safe = not state.get("safety_interlock_active", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_drilling_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "wellbore": state.get("wellbore_id"),
            "operational_status": "OPTIMAL" if is_safe else "MAINTENANCE_REQUIRED",
            "interlock_triggered": not is_safe,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("intake", intake_telemetry)
_g.add_node("analyze", analyze_safety_thresholds)
_g.add_node("finalize", finalize_drilling_state)

_g.add_edge(START, "intake")
_g.add_edge("intake", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
