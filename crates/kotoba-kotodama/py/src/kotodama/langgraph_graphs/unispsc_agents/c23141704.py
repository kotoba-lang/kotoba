# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23141704 — Compressor (segment 23).

Bespoke graph logic for industrial compressor systems. This agent manages
technical specifications, maintenance cycle tracking, and operational
certification validation for industrial-grade compression hardware.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23141704"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23141704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Compressor
    operating_pressure_psi: float
    maintenance_cycle_hours: int
    certification_status: str
    is_compliant: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Validates technical specs for the compressor unit."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 0.0))

    # Simple validation logic for industrial compressors
    is_compliant = pressure > 0 and pressure < 10000

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "operating_pressure_psi": pressure,
        "is_compliant": is_compliant,
        "certification_status": "PENDING"
    }


def schedule_maintenance(state: State) -> dict[str, Any]:
    """Determines maintenance intervals based on pressure and usage."""
    pressure = state.get("operating_pressure_psi", 0.0)

    # Higher pressure leads to more frequent maintenance cycles
    if pressure > 5000:
        cycle = 1000
    elif pressure > 1000:
        cycle = 3000
    else:
        cycle = 5000

    return {
        "log": [f"{UNISPSC_CODE}:schedule_maintenance"],
        "maintenance_cycle_hours": cycle,
        "certification_status": "VERIFIED" if state.get("is_compliant") else "REJECTED"
    }


def emit_profile(state: State) -> dict[str, Any]:
    """Compiles the final technical profile for the compressor agent."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_profile"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "pressure_psi": state.get("operating_pressure_psi"),
                "maintenance_hours": state.get("maintenance_cycle_hours"),
                "status": state.get("certification_status")
            },
            "ok": state.get("is_compliant", False)
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("maintenance", schedule_maintenance)
_g.add_node("emit", emit_profile)

_g.add_edge(START, "validate")
_g.add_edge("validate", "maintenance")
_g.add_edge("maintenance", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
