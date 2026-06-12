# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172004 — Shock Absorber (segment 25).

Bespoke graph logic for industrial shock absorber component validation.
This agent manages state transitions for physical inspection, performance
measurement, and final certification of shock absorber units.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172004"
UNISPSC_TITLE = "Shock Absorber"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields
    damping_coefficient: float
    internal_pressure_psi: float
    seal_integrity_verified: bool
    mounting_hardware_spec: str


def inspect_physical(state: State) -> dict[str, Any]:
    """Inspects the physical casing and seals for leaks."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 150.0))
    # Logic: shock absorbers must maintain pressure for operation
    passed = pressure > 100.0
    return {
        "log": [f"{UNISPSC_CODE}:inspect_physical:pressure={pressure}:integrity={passed}"],
        "internal_pressure_psi": pressure,
        "seal_integrity_verified": passed,
        "mounting_hardware_spec": inp.get("mounting", "Standard M12"),
    }


def measure_performance(state: State) -> dict[str, Any]:
    """Calculates damping performance based on input load."""
    if not state.get("seal_integrity_verified"):
        return {"log": [f"{UNISPSC_CODE}:measure_performance:skipped_due_to_leak"]}

    # Mock calculation for damping coefficient
    damping = 0.85 if state.get("internal_pressure_psi", 0) > 120 else 0.4
    return {
        "log": [f"{UNISPSC_CODE}:measure_performance:damping={damping}"],
        "damping_coefficient": damping,
    }


def certify_component(state: State) -> dict[str, Any]:
    """Finalizes the validation and emits the result."""
    valid = state.get("seal_integrity_verified", False) and state.get("damping_coefficient", 0.0) > 0.5

    return {
        "log": [f"{UNISPSC_CODE}:certify_component:valid={valid}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": valid,
            "metrics": {
                "pressure": state.get("internal_pressure_psi"),
                "damping": state.get("damping_coefficient"),
                "mounting": state.get("mounting_hardware_spec"),
            },
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_physical", inspect_physical)
_g.add_node("measure_performance", measure_performance)
_g.add_node("certify_component", certify_component)

_g.add_edge(START, "inspect_physical")
_g.add_edge("inspect_physical", "measure_performance")
_g.add_edge("measure_performance", "certify_component")
_g.add_edge("certify_component", END)

graph = _g.compile()
