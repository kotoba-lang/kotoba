# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101807 — Pump (segment 21).

Bespoke graph logic for handling pump-related procurement and technical specification
workflows. This agent validates pump requirements, assesses performance parameters,
and generates a structured technical specification result.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101807"
UNISPSC_TITLE = "Pump"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101807"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Pump
    flow_rate_lpm: float
    pressure_bar: float
    power_requirement_kw: float
    fluid_type: str
    is_valid: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Validate the input requirements for the pump specifications."""
    inp = state.get("input") or {}
    flow = float(inp.get("flow_rate", 0.0))
    pressure = float(inp.get("pressure", 0.0))
    fluid = str(inp.get("fluid", "water"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "flow_rate_lpm": flow,
        "pressure_bar": pressure,
        "fluid_type": fluid,
        "is_valid": flow > 0 and pressure > 0,
    }


def calculate_performance(state: State) -> dict[str, Any]:
    """Calculate the power requirements based on flow and pressure."""
    flow = state.get("flow_rate_lpm", 0.0)
    pressure = state.get("pressure_bar", 0.0)

    # Power (kW) = (Flow (L/min) * Pressure (Bar)) / 600
    # This is a standard approximation for hydraulic power
    power = (flow * pressure) / 600.0 if flow and pressure else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_performance"],
        "power_requirement_kw": round(power, 2),
    }


def finalize_specs(state: State) -> dict[str, Any]:
    """Prepare the final pump specification record."""
    valid = state.get("is_valid", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specs"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "flow_rate": state.get("flow_rate_lpm"),
                "pressure": state.get("pressure_bar"),
                "power_kw": state.get("power_requirement_kw"),
                "fluid": state.get("fluid_type"),
            },
            "verification_status": "certified" if valid else "insufficient_data",
            "ok": valid,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("calculate", calculate_performance)
_g.add_node("finalize", finalize_specs)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
