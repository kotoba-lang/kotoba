# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25181703 — Trailer (segment 25).

Bespoke logic for managing trailer specifications, safety certifications,
and transport manifests within the Etz Hayyim actor network.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25181703"
UNISPSC_TITLE = "Trailer"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25181703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Trailer
    trailer_type: str
    load_capacity_kg: float
    safety_inspection_passed: bool
    registration_id: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the physical specifications of the trailer unit."""
    inp = state.get("input") or {}
    t_type = inp.get("type", "standard_flatbed")
    capacity = float(inp.get("capacity", 25000.0))
    reg_id = inp.get("vin", "TRL-PENDING")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs -> {t_type}"],
        "trailer_type": t_type,
        "load_capacity_kg": capacity,
        "registration_id": reg_id,
    }


def perform_safety_check(state: State) -> dict[str, Any]:
    """Simulates a safety inspection protocol for the trailer."""
    capacity = state.get("load_capacity_kg", 0.0)
    # Logic: extreme loads require specialized inspections
    passed = capacity < 50000.0

    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_check -> {'PASSED' if passed else 'FAILED'}"],
        "safety_inspection_passed": passed,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final transport readiness manifest."""
    safe = state.get("safety_inspection_passed", False)
    t_type = state.get("trailer_type", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "ready_for_dispatch" if safe else "grounded",
            "metadata": {
                "trailer_type": t_type,
                "safety_certified": safe,
                "vin": state.get("registration_id"),
            },
            "ok": safe,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("perform_safety_check", perform_safety_check)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "perform_safety_check")
_g.add_edge("perform_safety_check", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
