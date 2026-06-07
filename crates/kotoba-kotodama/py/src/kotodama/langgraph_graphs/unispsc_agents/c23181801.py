# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181801 — Compressor (segment 23).

Bespoke logic for industrial compressor simulation and monitoring. This agent
models the thermodynamics of a compression cycle, validating intake conditions,
calculating compression ratios, and managing discharge parameters.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181801"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Compressor
    operating_pressure_psi: float
    flow_rate_scfm: float
    inlet_temperature_f: float
    compression_ratio: float
    is_operational: bool


def intake(state: State) -> dict[str, Any]:
    """Validate intake parameters and initialize compressor state."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 14.7))
    temp = float(inp.get("temperature", 70.0))
    flow = float(inp.get("flow", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:intake - P:{pressure}psi T:{temp}F F:{flow}scfm"],
        "operating_pressure_psi": pressure,
        "inlet_temperature_f": temp,
        "flow_rate_scfm": flow,
        "is_operational": True
    }


def compress(state: State) -> dict[str, Any]:
    """Perform compression stage logic and calculate ratios."""
    # Simulation of a standard 100 PSI discharge target
    target_pressure = 100.0
    initial_pressure = state.get("operating_pressure_psi", 14.7)

    # Calculate compression ratio (absolute pressure ratio)
    abs_initial = initial_pressure + 14.7
    abs_target = target_pressure + 14.7
    ratio = abs_target / abs_initial if abs_initial > 0 else 1.0

    return {
        "log": [f"{UNISPSC_CODE}:compress - ratio:{ratio:.2f}x"],
        "operating_pressure_psi": target_pressure,
        "compression_ratio": ratio
    }


def discharge(state: State) -> dict[str, Any]:
    """Finalize compressed air discharge and generate result metadata."""
    pressure = state.get("operating_pressure_psi", 0.0)
    flow = state.get("flow_rate_scfm", 0.0)
    ratio = state.get("compression_ratio", 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:discharge - final_P:{pressure}psi"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "discharge_pressure_psi": pressure,
                "delivered_flow_scfm": flow,
                "compression_ratio": round(ratio, 2)
            },
            "status": "nominal" if pressure >= 90 else "degraded",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("intake", intake)
_g.add_node("compress", compress)
_g.add_node("discharge", discharge)

_g.add_edge(START, "intake")
_g.add_edge("intake", "compress")
_g.add_edge("compress", "discharge")
_g.add_edge("discharge", END)

graph = _g.compile()
