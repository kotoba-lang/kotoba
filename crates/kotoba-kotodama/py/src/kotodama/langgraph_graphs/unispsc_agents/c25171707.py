# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171707 — Brake (segment 25).

Bespoke graph logic for vehicle brake components, handling specification
inspection, safety verification, and component finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171707"
UNISPSC_TITLE = "Brake"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171707"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Brake components
    safety_standard_compliant: bool
    wear_limit_mm: float
    material_spec: str
    inspection_status: str


def inspect_spec(state: State) -> dict[str, Any]:
    """Inspect the brake component specifications from input."""
    inp = state.get("input") or {}
    spec = inp.get("material", "unknown")
    limit = float(inp.get("wear_limit", 2.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_spec"],
        "material_spec": spec,
        "wear_limit_mm": limit,
        "inspection_status": "spec_checked"
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Verify safety standards based on the material and wear limits."""
    material = state.get("material_spec", "unknown")
    compliant = material.lower() in ["ceramic", "metallic", "organic"]

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "safety_standard_compliant": compliant,
        "inspection_status": "safety_verified" if compliant else "safety_failed"
    }


def finalize_component(state: State) -> dict[str, Any]:
    """Finalize the brake component data and emit result."""
    compliant = state.get("safety_standard_compliant", False)
    status = state.get("inspection_status", "incomplete")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_component"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "safety_ok": compliant,
            "status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_spec", inspect_spec)
_g.add_node("verify_safety", verify_safety)
_g.add_node("finalize_component", finalize_component)

_g.add_edge(START, "inspect_spec")
_g.add_edge("inspect_spec", "verify_safety")
_g.add_edge("verify_safety", "finalize_component")
_g.add_edge("finalize_component", END)

graph = _g.compile()
