# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171706 — Brake (segment 25).

Bespoke graph for automotive brake component inspection and safety validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171706"
UNISPSC_TITLE = "Brake"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171706"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific state for Brake hardware
    brake_type: str  # disc, drum, regenerative
    wear_coefficient: float
    fluid_pressure_kpa: float
    safety_status: str
    maintenance_required: bool


def inspect_hardware(state: State) -> dict[str, Any]:
    """Reads telemetry and determines hardware specifications."""
    inp = state.get("input") or {}
    wear = float(inp.get("wear", 0.15))
    pressure = float(inp.get("pressure", 850.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_hardware"],
        "brake_type": inp.get("type", "disc"),
        "wear_coefficient": wear,
        "fluid_pressure_kpa": pressure,
    }


def validate_safety(state: State) -> dict[str, Any]:
    """Checks tolerances for wear and hydraulic integrity."""
    wear = state.get("wear_coefficient", 0.0)
    pressure = state.get("fluid_pressure_kpa", 0.0)

    needs_service = wear > 0.75 or pressure < 500.0
    status = "REJECTED" if needs_service else "CERTIFIED"

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "safety_status": status,
        "maintenance_required": needs_service,
    }


def emit_report(state: State) -> dict[str, Any]:
    """Compiles the final safety report and certification result."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "safety_rating": state.get("safety_status"),
            "system_integrity": not state.get("maintenance_required"),
            "telemetry": {
                "wear": state.get("wear_coefficient"),
                "pressure": state.get("fluid_pressure_kpa"),
                "type": state.get("brake_type")
            }
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_hardware)
_g.add_node("validate", validate_safety)
_g.add_node("emit", emit_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "validate")
_g.add_edge("validate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
