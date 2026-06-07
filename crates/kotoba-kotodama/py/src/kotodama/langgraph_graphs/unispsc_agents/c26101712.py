# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101712 — Valve (segment 26).

Bespoke graph for industrial valve specification and certification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101712"
UNISPSC_TITLE = "Valve"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101712"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Valve
    valve_type: str
    material_grade: str
    pressure_rating_psi: float
    seal_integrity_verified: bool
    flow_coefficient_cv: float


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates the physical and technical specifications of the valve."""
    inp = state.get("input") or {}
    v_type = inp.get("type", "ball")
    material = inp.get("material", "316_stainless_steel")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "valve_type": v_type,
        "material_grade": material,
    }


def analyze_performance_rating(state: State) -> dict[str, Any]:
    """Calculates pressure tolerance and flow characteristics."""
    inp = state.get("input") or {}
    op_pressure = float(inp.get("operating_pressure", 150.0))

    # Simulated engineering logic for valve integrity
    is_compliant = False
    if state.get("material_grade") == "316_stainless_steel":
        is_compliant = op_pressure <= 600.0
    else:
        is_compliant = op_pressure <= 250.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance_rating"],
        "pressure_rating_psi": op_pressure,
        "seal_integrity_verified": is_compliant,
        "flow_coefficient_cv": 15.8 if state.get("valve_type") == "ball" else 8.4,
    }


def certify_unit(state: State) -> dict[str, Any]:
    """Generates the final compliance and certification payload."""
    status = "Certified" if state.get("seal_integrity_verified") else "Rejected"

    return {
        "log": [f"{UNISPSC_CODE}:certify_unit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": status,
            "specs": {
                "type": state.get("valve_type"),
                "material": state.get("material_grade"),
                "cv": state.get("flow_coefficient_cv"),
            },
            "ok": state.get("seal_integrity_verified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specifications)
_g.add_node("analyze", analyze_performance_rating)
_g.add_node("certify", certify_unit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
