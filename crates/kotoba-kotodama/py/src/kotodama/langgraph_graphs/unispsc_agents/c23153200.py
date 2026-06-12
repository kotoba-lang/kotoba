# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153200 — Weld (segment 23).

Bespoke graph logic for welding process coordination, focusing on material
specifications, joint configuration, and integrity verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153200"
UNISPSC_TITLE = "Weld"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153200"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Weld process
    weld_method: str
    material_type: str
    joint_integrity_checked: bool
    machine_status: str


def validate_weld_params(state: State) -> dict[str, Any]:
    """Validates input parameters for the welding task."""
    inp = state.get("input") or {}
    method = inp.get("method", "MIG")
    material = inp.get("material", "Steel")
    return {
        "log": [f"{UNISPSC_CODE}:validate_weld_params"],
        "weld_method": method,
        "material_type": material,
        "machine_status": "ready",
    }


def execute_weld_sequence(state: State) -> dict[str, Any]:
    """Simulates the physical welding operation."""
    method = state.get("weld_method", "unknown")
    material = state.get("material_type", "unknown")
    return {
        "log": [f"{UNISPSC_CODE}:execute_weld_sequence - {method} on {material}"],
        "machine_status": "completed",
        "joint_integrity_checked": True,
    }


def finalize_weld_output(state: State) -> dict[str, Any]:
    """Constructs the final response after verifying the weld."""
    is_ok = state.get("joint_integrity_checked", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_weld_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "method_used": state.get("weld_method"),
            "material": state.get("material_type"),
            "verified": is_ok,
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_weld_params)
_g.add_node("execute", execute_weld_sequence)
_g.add_node("finalize", finalize_weld_output)

_g.add_edge(START, "validate")
_g.add_edge("validate", "execute")
_g.add_edge("execute", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
