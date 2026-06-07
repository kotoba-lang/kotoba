# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121209 — Valve (segment 20).
Bespoke logic for industrial valve specification validation and pressure testing simulation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121209"
UNISPSC_TITLE = "Valve"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121209"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    specification_verified: bool
    pressure_test_passed: bool
    seal_integrity_score: float
    valve_type: str


def inspect_specification(state: State) -> dict[str, Any]:
    """Validates the valve technical specifications from the input metadata."""
    inp = state.get("input") or {}
    valve_type = inp.get("type", "ball_valve")
    has_pressure_rating = "pressure_rating" in inp
    has_material_spec = "material" in inp

    is_valid = has_pressure_rating and has_material_spec
    return {
        "log": [f"{UNISPSC_CODE}:inspect_specification: {valve_type} (valid={is_valid})"],
        "specification_verified": is_valid,
        "valve_type": valve_type,
    }


def perform_pressure_test(state: State) -> dict[str, Any]:
    """Simulates a static pressure test based on the verified specification."""
    if not state.get("specification_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:perform_pressure_test: aborting (spec unverified)"],
            "pressure_test_passed": False,
            "seal_integrity_score": 0.0,
        }

    inp = state.get("input") or {}
    target_psi = inp.get("pressure_rating", 0)

    # Logic: Assume success if pressure rating is within standard operating bounds
    test_success = 0 < target_psi <= 10000
    integrity = 0.99 if test_success else 0.45

    return {
        "log": [f"{UNISPSC_CODE}:perform_pressure_test: target={target_psi}psi status={test_success}"],
        "pressure_test_passed": test_success,
        "seal_integrity_score": integrity,
    }


def certify_valve(state: State) -> dict[str, Any]:
    """Issues a certification result based on inspection and test outcomes."""
    passed = state.get("pressure_test_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_valve: result={'certified' if passed else 'rejected'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": passed,
            "certification_metadata": {
                "valve_type": state.get("valve_type"),
                "seal_integrity": state.get("seal_integrity_score"),
                "compliant": passed,
            },
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_specification", inspect_specification)
_g.add_node("perform_pressure_test", perform_pressure_test)
_g.add_node("certify_valve", certify_valve)

_g.add_edge(START, "inspect_specification")
_g.add_edge("inspect_specification", "perform_pressure_test")
_g.add_edge("perform_pressure_test", "certify_valve")
_g.add_edge("certify_valve", END)

graph = _g.compile()
