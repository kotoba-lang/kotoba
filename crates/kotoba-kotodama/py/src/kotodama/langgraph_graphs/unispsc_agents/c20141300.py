# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141300 — Rock drilling machinery and accessories.

Bespoke graph logic for drilling mechanics validation and telemetry generation.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141300"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141300"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    borehole_depth_target: float
    rock_hardness_index: float
    bit_pressure_psi: float
    cooling_rate_lpm: float


def validate_rig_configuration(state: State) -> dict[str, Any]:
    """Validates site input and initializes drilling parameters."""
    inp = state.get("input") or {}
    depth = float(inp.get("depth", 100.0))
    hardness = float(inp.get("hardness", 5.5))
    return {
        "log": [f"{UNISPSC_CODE}:validate_rig_configuration"],
        "borehole_depth_target": depth,
        "rock_hardness_index": hardness,
    }


def calculate_drilling_mechanics(state: State) -> dict[str, Any]:
    """Computes necessary pressure and cooling rates based on site physics."""
    depth = state.get("borehole_depth_target", 0.0)
    hardness = state.get("rock_hardness_index", 0.0)

    # Calculate operational requirements based on depth and rock resistance
    required_psi = (depth * 1.2) + (hardness * 250.0)
    cooling_lpm = (depth * 0.15) + (hardness * 5.0)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_drilling_mechanics"],
        "bit_pressure_psi": required_psi,
        "cooling_rate_lpm": cooling_lpm,
    }


def generate_drilling_manifest(state: State) -> dict[str, Any]:
    """Finalizes the operational plan and emits the telemetry result."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_drilling_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "OPERATIONAL_READY",
            "telemetry": {
                "target_depth": state.get("borehole_depth_target"),
                "required_pressure": state.get("bit_pressure_psi"),
                "flow_rate": state.get("cooling_rate_lpm"),
            },
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_rig_configuration)
_g.add_node("calculate", calculate_drilling_mechanics)
_g.add_node("emit", generate_drilling_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
