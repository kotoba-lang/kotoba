# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24121800 — Packaging (segment 24).

This bespoke implementation provides a functional graph for packaging logistics,
simulating specification evaluation, integrity verification, and final record
emission within the Etz Hayyim actor substrate.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24121800"
UNISPSC_TITLE = "Packaging"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24121800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Packaging
    container_type: str
    material_grade: str
    specification_met: bool
    seal_integrity_verified: bool


def evaluate_specs(state: State) -> dict[str, Any]:
    """Inspects the input for packaging material requirements."""
    inp = state.get("input") or {}
    c_type = inp.get("container_type", "standard_corrugated")
    grade = inp.get("material_grade", "A")
    # Simulation: assume all 'A' or 'B' grades meet specifications
    is_valid = grade in ["A", "B"]

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_specs(type={c_type}, grade={grade})"],
        "container_type": c_type,
        "material_grade": grade,
        "specification_met": is_valid,
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Simulates a seal and durability verification process."""
    specs_ok = state.get("specification_met", False)
    # Verification fails if specifications were not met initially
    integrity_pass = specs_ok

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity(passed={integrity_pass})"],
        "seal_integrity_verified": integrity_pass,
    }


def finalize_packaging(state: State) -> dict[str, Any]:
    """Emits the final packaging status and metadata."""
    is_verified = state.get("seal_integrity_verified", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "ok": is_verified,
        "packaging_metadata": {
            "container": state.get("container_type"),
            "grade": state.get("material_grade"),
            "timestamp": "2026-05-23T14:00:00Z"
        },
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_packaging"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("evaluate_specs", evaluate_specs)
_g.add_node("verify_integrity", verify_integrity)
_g.add_node("finalize_packaging", finalize_packaging)

_g.add_edge(START, "evaluate_specs")
_g.add_edge("evaluate_specs", "verify_integrity")
_g.add_edge("verify_integrity", "finalize_packaging")
_g.add_edge("finalize_packaging", END)

graph = _g.compile()
