# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20131004 — Hydraulic (segment 20).

Bespoke logic for hydraulic systems modeling and verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20131004"
UNISPSC_TITLE = "Hydraulic"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20131004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Hydraulic systems
    pressure_psi: float
    flow_rate_gpm: float
    fluid_type: str
    safety_valve_active: bool
    inspection_passed: bool


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates input hydraulic parameters or sets defaults."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 2500.0))
    flow = float(inp.get("flow", 15.0))
    fluid = str(inp.get("fluid", "ISO VG 46"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "pressure_psi": pressure,
        "flow_rate_gpm": flow,
        "fluid_type": fluid,
        "safety_valve_active": pressure < 5000.0,
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Simulates performance analysis for the hydraulic circuit."""
    pressure = state.get("pressure_psi", 0.0)
    flow = state.get("flow_rate_gpm", 0.0)

    # Hydraulic Horsepower = (Pressure (PSI) * Flow (GPM)) / 1714
    hp_output = (pressure * flow) / 1714.0
    passed = pressure > 0 and hp_output < 250.0 # Arbitrary safety threshold

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance:HP_CALC={hp_output:.2f}"],
        "inspection_passed": passed,
    }


def generate_report(state: State) -> dict[str, Any]:
    """Compiles the final hydraulic system status report."""
    passed = state.get("inspection_passed", False)
    valve = state.get("safety_valve_active", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "system_status": "OPERATIONAL" if passed and valve else "MAINTENANCE_REQUIRED",
            "metrics": {
                "pressure_psi": state.get("pressure_psi"),
                "flow_gpm": state.get("flow_rate_gpm"),
                "fluid": state.get("fluid_type"),
            },
            "did": UNISPSC_DID,
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("analyze", analyze_performance)
_g.add_node("report", generate_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "report")
_g.add_edge("report", END)

graph = _g.compile()
