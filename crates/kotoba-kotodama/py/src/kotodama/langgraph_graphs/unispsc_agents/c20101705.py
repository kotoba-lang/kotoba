# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20101705 — Fastener (segment 20).

Bespoke graph for managing fastener specifications, torque calculations,
and batch integrity verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101705"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    spec_verification: bool
    torque_requirement: float
    material_grade: str
    thread_pitch: str
    integrity_status: str


def inspect_spec(state: State) -> dict[str, Any]:
    """Inspects fastener specifications for compliance."""
    inp = state.get("input") or {}
    spec_ok = "diameter" in inp and "length" in inp
    return {
        "log": [f"{UNISPSC_CODE}:inspect_spec"],
        "spec_verification": spec_ok,
        "material_grade": inp.get("grade", "Standard"),
        "thread_pitch": inp.get("pitch", "Coarse"),
    }


def calculate_torque(state: State) -> dict[str, Any]:
    """Calculates necessary torque requirements based on fastener specs."""
    inp = state.get("input") or {}
    diameter = float(inp.get("diameter", 1.0))
    # Simple mock torque formula: diameter * grade_multiplier
    grade_multipliers = {"Grade 5": 1.2, "Grade 8": 1.5, "Standard": 1.0}
    multiplier = grade_multipliers.get(state.get("material_grade", "Standard"), 1.0)
    torque = diameter * 20.0 * multiplier

    return {
        "log": [f"{UNISPSC_CODE}:calculate_torque"],
        "torque_requirement": torque,
        "integrity_status": "SPEC_PROCESSED",
    }


def finalize_batch(state: State) -> dict[str, Any]:
    """Finalizes the fastener batch and generates the result object."""
    is_valid = state.get("spec_verification", False)
    final_status = "CERTIFIED" if is_valid else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_batch"],
        "integrity_status": final_status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "torque_nm": state.get("torque_requirement"),
            "status": final_status,
            "ok": is_valid,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_spec", inspect_spec)
_g.add_node("calculate_torque", calculate_torque)
_g.add_node("finalize_batch", finalize_batch)

_g.add_edge(START, "inspect_spec")
_g.add_edge("inspect_spec", "calculate_torque")
_g.add_edge("calculate_torque", "finalize_batch")
_g.add_edge("finalize_batch", END)

graph = _g.compile()
