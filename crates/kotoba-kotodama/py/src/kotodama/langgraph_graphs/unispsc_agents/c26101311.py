# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101311 — Motor (segment 26).

Bespoke logic for electric motor specifications, safety certification,
and configuration management within the Etz Hayyim actor network.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101311"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101311"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke Motor State Fields
    nominal_voltage_v: float
    max_rpm: int
    frame_size: str
    is_explosion_proof: bool
    efficiency_rating: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the base technical specifications of the motor."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 460.0))
    rpm = int(inp.get("rpm", 3600))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "nominal_voltage_v": voltage,
        "max_rpm": rpm,
    }


def configure_safety(state: State) -> dict[str, Any]:
    """Applies safety and environment-specific configuration."""
    inp = state.get("input") or {}
    explosion_proof = bool(inp.get("explosion_proof", False))
    frame = str(inp.get("frame", "NEMA 56"))

    return {
        "log": [f"{UNISPSC_CODE}:configure_safety"],
        "is_explosion_proof": explosion_proof,
        "frame_size": frame,
    }


def calculate_efficiency(state: State) -> dict[str, Any]:
    """Determines the motor efficiency rating based on configured specs."""
    voltage = state.get("nominal_voltage_v", 0)
    # IE3 Premium Efficiency for standard voltages, IE2 for others
    rating = "IE3" if voltage >= 400 else "IE2"

    return {
        "log": [f"{UNISPSC_CODE}:calculate_efficiency"],
        "efficiency_rating": rating,
    }


def finalize(state: State) -> dict[str, Any]:
    """Finalizes the motor record with all validated parameters."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize"],
        "result": {
            "id": UNISPSC_DID,
            "metadata": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
                "segment": UNISPSC_SEGMENT,
            },
            "specs": {
                "voltage_v": state.get("nominal_voltage_v"),
                "rpm_max": state.get("max_rpm"),
                "frame": state.get("frame_size"),
                "explosion_proof": state.get("is_explosion_proof"),
                "efficiency": state.get("efficiency_rating"),
            },
            "status": "configured"
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("safety", configure_safety)
_g.add_node("efficiency", calculate_efficiency)
_g.add_node("finalize", finalize)

_g.add_edge(START, "validate")
_g.add_edge("validate", "safety")
_g.add_edge("safety", "efficiency")
_g.add_edge("efficiency", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
