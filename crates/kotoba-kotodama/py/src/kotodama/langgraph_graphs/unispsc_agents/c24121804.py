# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24121804"
UNISPSC_TITLE = "Food Can"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24121804"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for food packaging containers
    material_alloy: str
    nominal_capacity_ml: int
    lining_integrity_verified: bool
    vacuum_seal_status: str


def inspect_physical_specs(state: State) -> dict[str, Any]:
    """Inspects the physical material and capacity specifications of the food can."""
    inp = state.get("input") or {}
    alloy = inp.get("material", "Tin-Free Steel (TFS)")
    capacity = inp.get("capacity", 425)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_physical_specs -> {alloy}"],
        "material_alloy": alloy,
        "nominal_capacity_ml": capacity,
    }


def verify_lining_compliance(state: State) -> dict[str, Any]:
    """Validates the internal BPA-NI lining integrity and food-safety certification."""
    alloy = state.get("material_alloy", "")
    # Simulation: specific alloys require different lining verification logic
    is_compliant = len(alloy) > 0

    return {
        "log": [f"{UNISPSC_CODE}:verify_lining_compliance -> {is_compliant}"],
        "lining_integrity_verified": is_compliant,
    }


def test_hermetic_seal(state: State) -> dict[str, Any]:
    """Simulates vacuum testing to confirm the hermetic seal of the food can."""
    integrity = state.get("lining_integrity_verified", False)
    seal_ok = "Passed" if integrity else "Failed"

    return {
        "log": [f"{UNISPSC_CODE}:test_hermetic_seal -> {seal_ok}"],
        "vacuum_seal_status": seal_ok,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "audit": {
                "material": state.get("material_alloy"),
                "capacity": state.get("nominal_capacity_ml"),
                "lining_certified": integrity,
                "seal": seal_ok
            },
            "ready_for_filling": integrity and seal_ok == "Passed"
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_physical_specs)
_g.add_node("verify", verify_lining_compliance)
_g.add_node("test", test_hermetic_seal)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "test")
_g.add_edge("test", END)

graph = _g.compile()
