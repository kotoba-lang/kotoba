# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23121615 — Compressor (segment 23).

Bespoke graph logic for industrial compressor simulation and monitoring.
This agent handles inlet condition validation, compression stage physics
simulation, and telemetry output for the segment 23 industrial ecosystem.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23121615"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23121615"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    inlet_pressure_psi: float
    discharge_pressure_psi: float
    flow_rate_cfm: float
    discharge_temp_c: float
    is_operational: bool


def inspect_inlet(state: State) -> dict[str, Any]:
    """Validate incoming gas stream and compressor configuration."""
    inp = state.get("input") or {}
    pressure = float(inp.get("inlet_pressure", 14.7))
    flow = float(inp.get("target_flow", 150.0))

    # Simple check for mechanical readiness
    operational = pressure > 0 and flow > 0

    return {
        "log": [f"{UNISPSC_CODE}:inspect_inlet"],
        "inlet_pressure_psi": pressure,
        "flow_rate_cfm": flow,
        "is_operational": operational,
    }


def simulate_compression(state: State) -> dict[str, Any]:
    """Calculate discharge conditions based on compression ratios."""
    if not state.get("is_operational"):
        return {"log": [f"{UNISPSC_CODE}:simulate_compression_skipped"]}

    inlet_p = state.get("inlet_pressure_psi", 14.7)
    # Mocking a standard industrial compression ratio of 7.5
    discharge_p = inlet_p * 7.5

    # Simplified heat-of-compression calculation
    # T2 = T1 * (P2/P1)^((k-1)/k) -> simplified for mock logic
    ambient_temp = 25.0
    temp_rise = (discharge_p / inlet_p) * 12.0
    final_temp = ambient_temp + temp_rise

    return {
        "log": [f"{UNISPSC_CODE}:simulate_compression"],
        "discharge_pressure_psi": discharge_p,
        "discharge_temp_c": final_temp,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Package compressor performance data into the result payload."""
    is_ok = state.get("is_operational", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "data": {
                "inlet_pressure_psi": state.get("inlet_pressure_psi"),
                "discharge_pressure_psi": state.get("discharge_pressure_psi"),
                "flow_rate_cfm": state.get("flow_rate_cfm"),
                "discharge_temp_c": state.get("discharge_temp_c"),
                "status": "ACTIVE" if is_ok else "INACTIVE",
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_inlet)
_g.add_node("compress", simulate_compression)
_g.add_node("telemetry", finalize_telemetry)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "compress")
_g.add_edge("compress", "telemetry")
_g.add_edge("telemetry", END)

graph = _g.compile()
