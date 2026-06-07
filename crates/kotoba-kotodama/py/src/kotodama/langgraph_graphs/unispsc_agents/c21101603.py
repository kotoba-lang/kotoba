# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101603 — Radiator (segment 21).

Bespoke LangGraph implementation for Radiator components, focusing on
thermal performance validation, material integrity, and pressure rating certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101603"
UNISPSC_TITLE = "Radiator"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Radiator
    material_grade: str
    pressure_rating_psi: int
    coolant_compatibility: list[str]
    thermal_load_verified: bool
    qc_passed: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates the physical and material specifications of the radiator."""
    inp = state.get("input") or {}
    material = inp.get("material", "Aluminum-6061")
    rating = inp.get("pressure_limit", 30)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "material_grade": material,
        "pressure_rating_psi": rating,
        "coolant_compatibility": ["Ethylene Glycol", "Propylene Glycol", "Water"],
    }


def verify_thermal_performance(state: State) -> dict[str, Any]:
    """Simulates thermal dissipation efficiency based on fin density and material."""
    material = state.get("material_grade", "")
    # Logic: Aluminum has higher verified status in this simplified model
    verified = "Aluminum" in material or "Copper" in material

    return {
        "log": [f"{UNISPSC_CODE}:verify_thermal_performance"],
        "thermal_load_verified": verified,
    }


def certify_unit(state: State) -> dict[str, Any]:
    """Finalizes the certification for the radiator unit."""
    is_valid = state.get("thermal_load_verified", False) and state.get("pressure_rating_psi", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:certify_unit"],
        "qc_passed": is_valid,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certification": "ISO-9001-RAD" if is_valid else "PENDING",
            "material": state.get("material_grade"),
            "status": "APPROVED" if is_valid else "REJECTED",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specifications)
_g.add_node("verify", verify_thermal_performance)
_g.add_node("certify", certify_unit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
