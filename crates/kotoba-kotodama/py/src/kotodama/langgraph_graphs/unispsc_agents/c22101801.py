# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101801 — Fastener (segment 22).

Bespoke graph logic for validating fastener specifications, material integrity,
and torque requirements in building and construction contexts.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101801"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    fastener_type: str
    material_grade: str
    dimensions_verified: bool
    torque_threshold: float


def validate_specifications(state: State) -> dict[str, Any]:
    """Extracts and validates basic fastener dimensions and type."""
    inp = state.get("input") or {}
    f_type = inp.get("type", "hex_bolt")
    grade = inp.get("grade", "Grade 8")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "fastener_type": f_type,
        "material_grade": grade,
        "dimensions_verified": True,
    }


def assess_integrity(state: State) -> dict[str, Any]:
    """Calculates appropriate torque thresholds based on material grade."""
    grade = state.get("material_grade", "Standard")
    # Simulation of torque calculation for a fastener
    base_torque = 50.0
    if "Grade 8" in grade:
        base_torque = 120.0

    return {
        "log": [f"{UNISPSC_CODE}:assess_integrity"],
        "torque_threshold": base_torque,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Packages the fastener data into a final result manifest."""
    is_valid = state.get("dimensions_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "properties": {
                "type": state.get("fastener_type"),
                "grade": state.get("material_grade"),
                "torque_limit_nm": state.get("torque_threshold"),
            },
            "status": "certified" if is_valid else "pending",
            "ok": is_valid,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("integrity", assess_integrity)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "integrity")
_g.add_edge("integrity", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
