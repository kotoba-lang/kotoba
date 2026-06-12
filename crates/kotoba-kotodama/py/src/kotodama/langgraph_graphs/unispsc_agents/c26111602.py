# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111602 — Hydro Gen (segment 26).

Bespoke LangGraph implementation for Hydroelectric Generator modeling and
operational state management. This agent simulates the configuration,
hydraulic computation, and safety validation for hydro power units.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111602"
UNISPSC_TITLE = "Hydro Gen"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Hydro Gen
    turbine_type: str  # e.g., Francis, Kaplan, Pelton
    head_m: float      # Effective head height in meters
    flow_m3s: float    # Water flow rate in m^3/s
    power_mw: float    # Calculated power output in MegaWatts
    safety_clearance: bool


def configure_generator(state: State) -> dict[str, Any]:
    """Initializes generator specifications from input data."""
    inp = state.get("input") or {}
    t_type = inp.get("turbine_type", "Francis")
    head = float(inp.get("head_m", 100.0))
    flow = float(inp.get("flow_m3s", 50.0))

    return {
        "log": [f"{UNISPSC_CODE}:configure_generator_type:{t_type}"],
        "turbine_type": t_type,
        "head_m": head,
        "flow_m3s": flow,
    }


def compute_hydraulics(state: State) -> dict[str, Any]:
    """Calculates theoretical power output based on head and flow."""
    # P = eta * rho * g * h * dot_V
    # Simplified: 0.9 (eff) * 1000 (kg/m3) * 9.81 * head * flow / 1e6 (MW)
    efficiency = 0.91
    gravity = 9.81
    density = 1000.0

    head = state.get("head_m", 0.0)
    flow = state.get("flow_m3s", 0.0)

    power = (efficiency * density * gravity * head * flow) / 1_000_000.0

    return {
        "log": [f"{UNISPSC_CODE}:compute_hydraulics:output_{power:.2f}MW"],
        "power_mw": power,
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Validates operational parameters against safety thresholds."""
    power = state.get("power_mw", 0.0)
    # Assume a max rating of 500MW for this unit model
    safe = 0.0 < power < 500.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety:clearance_{safe}"],
        "safety_clearance": safe,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Packages the final state into a standardized result format."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "power_mw": state.get("power_mw"),
                "turbine": state.get("turbine_type"),
                "head": state.get("head_m"),
            },
            "status": "OPERATIONAL" if state.get("safety_clearance") else "OFFLINE",
            "ok": state.get("safety_clearance", False),
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_generator)
_g.add_node("compute", compute_hydraulics)
_g.add_node("verify", verify_safety)
_g.add_node("finalize", finalize_telemetry)

_g.add_edge(START, "configure")
_g.add_edge("configure", "compute")
_g.add_edge("compute", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
