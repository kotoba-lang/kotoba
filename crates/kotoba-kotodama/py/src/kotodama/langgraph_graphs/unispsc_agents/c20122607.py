# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122607 — Valve (segment 20).

Bespoke graph logic for industrial valve lifecycle management, including
specification validation, integrity testing, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122607"
UNISPSC_TITLE = "Valve"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122607"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Valve
    pressure_rating_psi: int
    seal_integrity_verified: bool
    material_grade: str
    maintenance_status: str


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates the mechanical specifications of the valve unit."""
    inp = state.get("input") or {}
    pressure = inp.get("pressure_rating", 150)
    material = inp.get("material", "Carbon Steel")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "pressure_rating_psi": pressure,
        "material_grade": material,
        "maintenance_status": "inspected",
    }


def test_integrity(state: State) -> dict[str, Any]:
    """Simulates pressure and seal integrity testing for the valve."""
    # Logic simulating a successful test based on specifications
    pressure = state.get("pressure_rating_psi", 0)
    integrity = pressure > 0 and pressure < 10000  # Within safety bounds

    return {
        "log": [f"{UNISPSC_CODE}:test_integrity"],
        "seal_integrity_verified": integrity,
        "maintenance_status": "tested",
    }


def certify_valve(state: State) -> dict[str, Any]:
    """Finalizes the valve record with compliance certification."""
    is_verified = state.get("seal_integrity_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_valve"],
        "maintenance_status": "certified" if is_verified else "failed",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_verified,
            "material": state.get("material_grade"),
            "rating": state.get("pressure_rating_psi"),
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specifications)
_g.add_node("test", test_integrity)
_g.add_node("certify", certify_valve)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "test")
_g.add_edge("test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
