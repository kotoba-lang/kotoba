# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101710 — Carb (segment 26).

This agent manages state transitions for Carburetor components in power
generation machinery. It validates intake parameters, calculates venturi
pressure dynamics, and emits calibration diagnostics.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101710"
UNISPSC_TITLE = "Carb"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101710"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    airflow_cfm: float
    fuel_rate_gph: float
    venturi_vacuum_hg: float
    mixture_ratio: float
    calibration_valid: bool


def inspect_carb_input(state: State) -> dict[str, Any]:
    """Validates the raw sensor or command input for carburetor state."""
    inp = state.get("input") or {}
    cfm = float(inp.get("airflow_cfm", 0.0))
    gph = float(inp.get("fuel_rate_gph", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_carb_input"],
        "airflow_cfm": cfm,
        "fuel_rate_gph": gph,
    }


def compute_mixture_dynamics(state: State) -> dict[str, Any]:
    """Simulates internal fluid dynamics to determine mixture health."""
    cfm = state.get("airflow_cfm", 0.0)
    gph = state.get("fuel_rate_gph", 0.0)

    # Simplified Bernoulli/Venturi model
    vacuum = (cfm * 0.02) if cfm > 0 else 0.0
    ratio = (cfm / gph) if gph > 0 else 0.0

    # Stoichiometric air-fuel ratio target range for efficiency
    is_valid = 12.0 <= ratio <= 16.0

    return {
        "log": [f"{UNISPSC_CODE}:compute_mixture_dynamics"],
        "venturi_vacuum_hg": vacuum,
        "mixture_ratio": ratio,
        "calibration_valid": is_valid,
    }


def emit_calibration_result(state: State) -> dict[str, Any]:
    """Finalizes the agent run and outputs a structured diagnostic result."""
    valid = state.get("calibration_valid", False)
    ratio = state.get("mixture_ratio", 0.0)
    vacuum = state.get("venturi_vacuum_hg", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:emit_calibration_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "diagnostics": {
                "air_fuel_ratio": round(ratio, 2),
                "venturi_vacuum": round(vacuum, 2),
                "status": "PASS" if valid else "RECALIBRATE"
            },
            "ok": valid,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_carb_input)
_g.add_node("compute", compute_mixture_dynamics)
_g.add_node("emit", emit_calibration_result)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "compute")
_g.add_edge("compute", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
