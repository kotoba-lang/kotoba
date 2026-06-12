# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101511"
UNISPSC_TITLE = "Turbine"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101511"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Turbine domain state fields
    thermal_gradient_c: float
    blade_integrity_index: float
    lubrication_level: str
    is_operational: bool


def inspect_turbine_parameters(state: State) -> dict[str, Any]:
    """Validate input parameters for turbine operation and safety limits."""
    inp = state.get("input") or {}
    gradient = float(inp.get("thermal_gradient", 150.0))
    lubrication = str(inp.get("lubrication", "nominal"))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_turbine_parameters"],
        "thermal_gradient_c": gradient,
        "lubrication_level": lubrication,
        "is_operational": False,
    }


def simulate_mechanical_stress(state: State) -> dict[str, Any]:
    """Calculate mechanical stress and blade integrity based on heat delta."""
    gradient = state.get("thermal_gradient_c", 0.0)
    # Integrity decreases as thermal gradient increases beyond material limits
    integrity = max(0.0, 1.0 - (gradient / 1200.0))
    return {
        "log": [f"{UNISPSC_CODE}:simulate_mechanical_stress"],
        "blade_integrity_index": integrity,
    }


def certify_operation(state: State) -> dict[str, Any]:
    """Finalize certification status based on integrity and auxiliary systems."""
    integrity = state.get("blade_integrity_index", 0.0)
    lubrication = state.get("lubrication_level", "")
    operational = integrity > 0.75 and lubrication == "nominal"

    return {
        "log": [f"{UNISPSC_CODE}:certify_operation"],
        "is_operational": operational,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certification": "GRANTED" if operational else "DENIED",
            "integrity_score": round(integrity, 4),
            "ok": operational,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_turbine_parameters)
_g.add_node("stress_test", simulate_mechanical_stress)
_g.add_node("certify", certify_operation)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "stress_test")
_g.add_edge("stress_test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
