# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151809 — Compressor (segment 23).
Provides specialized logic for industrial compression systems specifications and maintenance cycles.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151809"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151809"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    pressure_rating_psi: float
    volumetric_flow_cfm: float
    maintenance_interval_hrs: int
    is_industrial_grade: bool


def configure_specs(state: State) -> dict[str, Any]:
    """Initializes and sanitizes compressor specification inputs."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 125.0))
    flow = float(inp.get("flow", 10.0))
    return {
        "log": [f"{UNISPSC_CODE}:configure_specs"],
        "pressure_rating_psi": pressure,
        "volumetric_flow_cfm": flow,
    }


def validate_duty_cycle(state: State) -> dict[str, Any]:
    """Determines industrial classification and service requirements based on specs."""
    pressure = state.get("pressure_rating_psi", 0.0)
    flow = state.get("volumetric_flow_cfm", 0.0)

    # Classify as industrial if high demand parameters are met
    is_industrial = pressure > 175.0 or flow > 50.0
    interval = 4000 if is_industrial else 1000

    return {
        "log": [f"{UNISPSC_CODE}:validate_duty_cycle"],
        "is_industrial_grade": is_industrial,
        "maintenance_interval_hrs": interval,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Compiles the final configuration manifest for the compressor unit."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "configuration": {
                "pressure_psi": state.get("pressure_rating_psi"),
                "flow_cfm": state.get("volumetric_flow_cfm"),
                "grade": "Industrial" if state.get("is_industrial_grade") else "Standard",
                "next_service_interval": state.get("maintenance_interval_hrs"),
            },
            "certified": True,
        },
    }


_g = StateGraph(State)

_g.add_node("configure_specs", configure_specs)
_g.add_node("validate_duty_cycle", validate_duty_cycle)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "configure_specs")
_g.add_edge("configure_specs", "validate_duty_cycle")
_g.add_edge("validate_duty_cycle", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
