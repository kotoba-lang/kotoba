# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101719"
UNISPSC_TITLE = "Supercharger"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101719"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Supercharger
    engine_rpm: int
    boost_pressure_psi: float
    intake_air_temp_c: float
    bypass_valve_open: bool
    compressor_efficiency: float


def inspect_parameters(state: State) -> dict[str, Any]:
    """Analyzes engine state to determine if supercharging is viable."""
    inp = state.get("input") or {}
    rpm = inp.get("rpm", 0)
    temp = inp.get("temp_c", 20.0)

    # Supercharger bypass opens at low RPM or high heat to protect the engine
    bypass = rpm < 1200 or temp > 110.0

    return {
        "log": [f"{UNISPSC_CODE}:inspect_parameters"],
        "engine_rpm": rpm,
        "intake_air_temp_c": temp,
        "bypass_valve_open": bypass,
    }


def apply_compression(state: State) -> dict[str, Any]:
    """Calculates manifold pressure based on compressor curves."""
    rpm = state.get("engine_rpm", 0)
    temp = state.get("intake_air_temp_c", 20.0)
    is_bypassed = state.get("bypass_valve_open", True)

    if is_bypassed:
        boost = 0.0
        efficiency = 0.0
    else:
        # Heuristic boost calculation: ~1 PSI per 500 RPM above 1200
        boost = (rpm - 1200) / 500.0
        # Efficiency drops as temperature rises
        efficiency = max(0.5, 0.95 - (temp / 200.0))

    return {
        "log": [f"{UNISPSC_CODE}:apply_compression"],
        "boost_pressure_psi": round(boost, 2),
        "compressor_efficiency": round(efficiency, 3),
    }


def emit_diagnostics(state: State) -> dict[str, Any]:
    """Constructs the final telemetry payload for the supercharger unit."""
    boost = state.get("boost_pressure_psi", 0.0)
    is_active = boost > 0.1

    return {
        "log": [f"{UNISPSC_CODE}:emit_diagnostics"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "active": is_active,
                "boost_psi": boost,
                "rpm": state.get("engine_rpm", 0),
                "efficiency": state.get("compressor_efficiency", 0.0),
            },
            "status": "boosting" if is_active else "standby",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_parameters)
_g.add_node("compress", apply_compression)
_g.add_node("emit", emit_diagnostics)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "compress")
_g.add_edge("compress", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
