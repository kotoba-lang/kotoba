# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21111602 — Irrigation Valve (segment 21).

Bespoke logic for irrigation valve control and monitoring, facilitating
automated pressure validation and flow rate simulation within the
Etz Hayyim actor ecosystem.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21111602"
UNISPSC_TITLE = "Irrigation Valve"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21111602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Irrigation Valve
    valve_position: str  # OPEN, CLOSED, or percentage
    pressure_psi: float
    flow_rate_gpm: float
    actuation_success: bool
    diagnostic_code: str


def validate_parameters(state: State) -> dict[str, Any]:
    """Analyzes input payload to establish baseline irrigation parameters."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 45.0))
    flow = float(inp.get("flow", 12.5))

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters (P:{pressure} F:{flow})"],
        "pressure_psi": pressure,
        "flow_rate_gpm": flow,
        "diagnostic_code": "VALVE_INIT_OK",
    }


def simulate_actuation(state: State) -> dict[str, Any]:
    """Simulates the physical response of the valve to requested state changes."""
    pressure = state.get("pressure_psi", 0.0)

    # Irrigation valves typically operate safely between 20 and 100 PSI
    if 20.0 <= pressure <= 100.0:
        success = True
        position = "OPEN"
        diag = "ACTUATION_NORMAL"
    else:
        success = False
        position = "CLOSED_SAFETY_TRIP"
        diag = "ERR_PRESSURE_OUT_OF_BOUNDS"

    return {
        "log": [f"{UNISPSC_CODE}:simulate_actuation ({position})"],
        "valve_position": position,
        "actuation_success": success,
        "diagnostic_code": diag,
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    """Compiles the operational status into a standardized result object."""
    success = state.get("actuation_success", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "telemetry": {
            "valve_position": state.get("valve_position"),
            "pressure": state.get("pressure_psi"),
            "flow": state.get("flow_rate_gpm"),
            "diagnostic": state.get("diagnostic_code"),
        },
        "ok": success,
    }

    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("actuate", simulate_actuation)
_g.add_node("emit", generate_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "actuate")
_g.add_edge("actuate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
