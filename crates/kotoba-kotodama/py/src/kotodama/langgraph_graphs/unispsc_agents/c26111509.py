# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111509 — Lithium Batteries.

This agent handles specifications validation and safety certification checks for
Lithium Battery components within segment 26 (Power Generation).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111509"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Lithium Batteries
    nominal_voltage: float
    capacity_mah: int
    chemistry_type: str
    safety_certified: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Extract and validate the technical specifications of the lithium battery."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 3.7))
    capacity = int(inp.get("capacity", 2000))
    chemistry = str(inp.get("chemistry", "Li-ion"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications -> {voltage}V, {capacity}mAh"],
        "nominal_voltage": voltage,
        "capacity_mah": capacity,
        "chemistry_type": chemistry,
    }


def assess_safety_compliance(state: State) -> dict[str, Any]:
    """Assess if the battery specs meet standard safety ranges."""
    v = state.get("nominal_voltage", 0.0)
    # Simulation: Basic voltage range check for single-cell lithium
    is_compliant = 3.0 <= v <= 4.2

    return {
        "log": [f"{UNISPSC_CODE}:assess_safety_compliance -> compliant: {is_compliant}"],
        "safety_certified": is_compliant,
    }


def finalize_registration(state: State) -> dict[str, Any]:
    """Finalize the registry entry for the lithium battery product."""
    is_ok = state.get("safety_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_registration"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "voltage": state.get("nominal_voltage"),
                "capacity": state.get("capacity_mah"),
                "chemistry": state.get("chemistry_type"),
                "certified": is_ok,
            },
            "status": "approved" if is_ok else "rejected",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("assess", assess_safety_compliance)
_g.add_node("finalize", finalize_registration)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
