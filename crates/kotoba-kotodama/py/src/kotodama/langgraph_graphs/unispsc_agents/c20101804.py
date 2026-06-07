# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20101804 — Acetylene (segment 20).

Bespoke graph for handling Acetylene gas state transitions, focusing on
purity validation, pressure monitoring, and safety compliance for
industrial distribution.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101804"
UNISPSC_TITLE = "Acetylene"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101804"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Acetylene
    purity_pct: float
    pressure_psi: float
    solvent_stabilized: bool
    safety_audit_passed: bool


def validate_purity(state: State) -> dict[str, Any]:
    """Inspects gas purity and stabilization state."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 98.0))
    stabilized = inp.get("solvent", "acetone") in ["acetone", "dmf"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_purity"],
        "purity_pct": purity,
        "solvent_stabilized": stabilized
    }


def verify_pressure_safety(state: State) -> dict[str, Any]:
    """Checks pressure limits; Acetylene is unstable above 15 psi if not handled correctly."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 14.5))

    # Simple safety logic: must be stabilized and within pressure bounds
    is_safe = state.get("solvent_stabilized", False) and pressure < 250.0  # Cylinder pressure vs line pressure
    if pressure > 15.0 and not state.get("solvent_stabilized"):
        is_safe = False

    return {
        "log": [f"{UNISPSC_CODE}:verify_pressure_safety"],
        "pressure_psi": pressure,
        "safety_audit_passed": is_safe
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final distribution result for the Acetylene batch."""
    is_ok = state.get("safety_audit_passed", False) and state.get("purity_pct", 0) > 95.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purity": state.get("purity_pct"),
            "safe_for_transport": is_ok,
            "status": "APPROVED" if is_ok else "REJECTED"
        },
    }


_g = StateGraph(State)

_g.add_node("validate_purity", validate_purity)
_g.add_node("verify_pressure_safety", verify_pressure_safety)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "validate_purity")
_g.add_edge("validate_purity", "verify_pressure_safety")
_g.add_edge("verify_pressure_safety", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
