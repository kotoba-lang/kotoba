# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122816 — Valve (segment 20).

Bespoke logic for managing valve specifications, pressure testing, and
certification records within the Etz Hayyim actor model.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122816"
UNISPSC_TITLE = "Valve"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122816"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    pressure_rating_psi: int
    material_compliance: bool
    valve_type: str
    certification_status: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the valve material and type from input payload."""
    inp = state.get("input") or {}
    v_type = inp.get("valve_type", "unknown")
    material = inp.get("material", "standard")

    compliance = material.lower() in ["steel", "brass", "bronze", "pvc"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications(type={v_type}, compliant={compliance})"],
        "valve_type": v_type,
        "material_compliance": compliance,
    }


def simulated_pressure_test(state: State) -> dict[str, Any]:
    """Simulates a pressure integrity test based on input requirements."""
    inp = state.get("input") or {}
    target_psi = inp.get("required_psi", 150)

    # Logic: PVC can't handle high pressure in this simulation
    is_pvc = state.get("valve_type") == "pvc"
    test_passed = not (is_pvc and target_psi > 100)

    status = "PASSED" if test_passed else "FAILED"

    return {
        "log": [f"{UNISPSC_CODE}:simulated_pressure_test(target={target_psi}, result={status})"],
        "pressure_rating_psi": target_psi if test_passed else 0,
        "certification_status": "PENDING_CERT" if test_passed else "REJECTED",
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Finalizes the valve record and generates the actor result."""
    passed = state.get("certification_status") == "PENDING_CERT"
    final_status = "CERTIFIED" if passed else "FAILED_INSPECTION"

    return {
        "log": [f"{UNISPSC_CODE}:emit_certification(status={final_status})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "valve_type": state.get("valve_type"),
            "pressure_rating": state.get("pressure_rating_psi"),
            "certified": passed,
            "status": final_status,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("pressure_test", simulated_pressure_test)
_g.add_node("certify", emit_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "pressure_test")
_g.add_edge("pressure_test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
