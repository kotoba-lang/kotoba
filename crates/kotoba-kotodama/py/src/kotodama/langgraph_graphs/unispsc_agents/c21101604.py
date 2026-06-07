# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101604 — Spray Equipment (segment 21).

Bespoke graph for managing industrial spray equipment operations, providing
automated pressure regulation, nozzle calibration, and safety verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101604"
UNISPSC_TITLE = "Spray Equipment"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific equipment state
    pressure_psi: float
    nozzle_id: str
    tank_fill_level: float
    safety_override: bool


def validate_setup(state: State) -> dict[str, Any]:
    """Validates the input configuration and initializes equipment sensors."""
    inp = state.get("input") or {}
    target_psi = float(inp.get("pressure", 40.0))
    nozzle = str(inp.get("nozzle", "TX-8001"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_setup -> psi={target_psi}, nozzle={nozzle}"],
        "pressure_psi": target_psi,
        "nozzle_id": nozzle,
        "tank_fill_level": 100.0,
        "safety_override": False,
    }


def calibrate_and_spray(state: State) -> dict[str, Any]:
    """Calibrates the nozzle and simulates the spraying process."""
    # Simulation: each spray cycle consumes a percentage of the tank
    current_level = state.get("tank_fill_level", 100.0)
    consumed = 12.5
    new_level = max(0.0, current_level - consumed)

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_and_spray -> new_tank_level={new_level}%"],
        "tank_fill_level": new_level,
    }


def emit_telemetry(state: State) -> dict[str, Any]:
    """Compiles the operational telemetry and locks the equipment."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_telemetry"],
        "safety_override": True,  # Engage safety lock after operation
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": True,
            "data": {
                "final_pressure": state.get("pressure_psi"),
                "nozzle_deployed": state.get("nozzle_id"),
                "remaining_volume": state.get("tank_fill_level"),
                "operation_status": "SUCCESS",
            },
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_setup)
_g.add_node("spray", calibrate_and_spray)
_g.add_node("emit", emit_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "spray")
_g.add_edge("spray", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
