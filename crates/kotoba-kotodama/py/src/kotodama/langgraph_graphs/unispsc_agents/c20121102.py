# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121102 — Pump (segment 20).

This module provides bespoke logic for managing industrial pump state,
simulating specification validation, safety interlock verification, and
operational telemetry processing within a LangGraph workflow.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121102"
UNISPSC_TITLE = "Pump"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121102"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Pump
    flow_rate_gpm: float
    pressure_psi: float
    safety_interlock_active: bool
    maintenance_status: str
    efficiency_rating: float


def validate_specs(state: State) -> dict[str, Any]:
    """Validates pump input specifications and initializes telemetry."""
    inp = state.get("input") or {}
    flow = float(inp.get("flow_rate", 0.0))
    pressure = float(inp.get("pressure", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs -> Flow: {flow} GPM, Pressure: {pressure} PSI"],
        "flow_rate_gpm": flow,
        "pressure_psi": pressure,
        "safety_interlock_active": inp.get("safety_override", False) is False,
        "maintenance_status": "nominal" if flow < 500 else "high_load_warning"
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Ensures safety protocols are met before processing telemetry."""
    is_safe = state.get("safety_interlock_active", False)
    status = "safety_cleared" if is_safe else "safety_breach_detected"

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety -> {status}"],
        "efficiency_rating": 0.92 if is_safe else 0.0
    }


def compute_telemetry(state: State) -> dict[str, Any]:
    """Generates the final pump operational report."""
    flow = state.get("flow_rate_gpm", 0.0)
    pressure = state.get("pressure_psi", 0.0)
    eff = state.get("efficiency_rating", 0.0)
    status = state.get("maintenance_status", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:compute_telemetry -> finalized"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "dynamic_head": pressure * 2.31,
                "power_requirement_bhp": (flow * pressure) / (1714 * eff) if eff > 0 else 0,
                "status": status,
            },
            "ok": eff > 0,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specs)
_g.add_node("verify", verify_safety)
_g.add_node("compute", compute_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "compute")
_g.add_edge("compute", END)

graph = _g.compile()
