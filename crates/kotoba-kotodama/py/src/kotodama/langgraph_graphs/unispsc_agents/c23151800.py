# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151800"
UNISPSC_TITLE = "Engine Proc"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Engine Proc domain
    compression_ratio: float
    thermal_load_verified: bool
    injection_timing_ms: float
    manifold_pressure_kpa: float


def validate_thermodynamics(state: State) -> dict[str, Any]:
    """Inspects input parameters for thermodynamic validity."""
    inp = state.get("input") or {}
    ratio = float(inp.get("compression_ratio", 9.5))
    return {
        "log": [f"{UNISPSC_CODE}:validate_thermodynamics"],
        "compression_ratio": ratio,
        "thermal_load_verified": 8.0 <= ratio <= 15.0,
    }


def simulate_combustion_cycle(state: State) -> dict[str, Any]:
    """Calculates injection and manifold dynamics based on validated ratios."""
    ratio = state.get("compression_ratio", 1.0)
    # Heuristic: higher compression requires advanced timing
    timing = 1.2 if ratio > 12.0 else 0.8
    pressure = 101.3 * (ratio / 10.0)
    return {
        "log": [f"{UNISPSC_CODE}:simulate_combustion_cycle"],
        "injection_timing_ms": timing,
        "manifold_pressure_kpa": pressure,
    }


def certify_engine_proc(state: State) -> dict[str, Any]:
    """Finalizes the engine processing report and certification."""
    is_valid = state.get("thermal_load_verified", False)
    pressure = state.get("manifold_pressure_kpa", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:certify_engine_proc"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if is_valid and pressure > 50 else "REJECTED",
            "metrics": {
                "p_manifold": f"{pressure:.2f} kPa",
                "timing": f"{state.get('injection_timing_ms', 0):.2f} ms"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_thermodynamics)
_g.add_node("simulate", simulate_combustion_cycle)
_g.add_node("certify", certify_engine_proc)

_g.add_edge(START, "validate")
_g.add_edge("validate", "simulate")
_g.add_edge("simulate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
