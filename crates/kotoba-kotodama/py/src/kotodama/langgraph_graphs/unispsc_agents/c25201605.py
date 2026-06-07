# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201605 — Aircraft Control.
Implements flight parameter validation, control surface adjustment calculation,
and telemetry reporting logic within a LangGraph state machine.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201605"
UNISPSC_TITLE = "Aircraft Control"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    altitude: float
    airspeed: float
    heading: float
    control_vetted: bool


def validate_parameters(state: State) -> dict[str, Any]:
    """Inspects incoming telemetry for safety violations and extracts parameters."""
    inp = state.get("input") or {}
    alt = float(inp.get("altitude", 0.0))
    speed = float(inp.get("airspeed", 0.0))
    hdg = float(inp.get("heading", 0.0))

    # Basic envelope check (e.g., standard commercial flight ceiling)
    in_envelope = 0.0 <= alt <= 45000.0 and 0.0 <= speed <= 950.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "altitude": alt,
        "airspeed": speed,
        "heading": hdg,
        "control_vetted": in_envelope,
    }


def calculate_corrections(state: State) -> dict[str, Any]:
    """Calculates control surface adjustments based on vetted telemetry."""
    vetted = state.get("control_vetted", False)
    status = "nominal_flight" if vetted else "corrective_action_required"

    return {
        "log": [f"{UNISPSC_CODE}:calculate_corrections:{status}"]
    }


def transmit_status(state: State) -> dict[str, Any]:
    """Generates the final aircraft control status report."""
    vetted = state.get("control_vetted", False)
    return {
        "log": [f"{UNISPSC_CODE}:transmit_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry_summary": {
                "alt": state.get("altitude"),
                "spd": state.get("airspeed"),
                "hdg": state.get("heading"),
            },
            "system_integrity": "high" if vetted else "degraded",
            "ok": vetted,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_parameters)
_g.add_node("calculate", calculate_corrections)
_g.add_node("transmit", transmit_status)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "transmit")
_g.add_edge("transmit", END)

graph = _g.compile()
