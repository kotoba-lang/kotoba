# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111721 — Battery (segment 26).

Bespoke logic for battery specification validation, charge state verification,
and inventory registration within the Unispsc actor framework.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111721"
UNISPSC_TITLE = "Battery"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111721"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Batteries
    voltage: float
    capacity_ah: float
    chemistry: str
    charge_state: float
    is_compliant: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the electrical specifications of the battery unit."""
    inp = state.get("input") or {}
    v = float(inp.get("voltage", 0.0))
    cap = float(inp.get("capacity_ah", 0.0))
    chem = str(inp.get("chemistry", "Lithium-Ion"))

    # Simple compliance logic: requires non-zero voltage and capacity
    compliant = v > 0 and cap > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "voltage": v,
        "capacity_ah": cap,
        "chemistry": chem,
        "is_compliant": compliant,
    }


def verify_charge(state: State) -> dict[str, Any]:
    """Calculates or verifies the current state of charge."""
    inp = state.get("input") or {}
    # Default to 1.0 (100%) if not provided
    soc = float(inp.get("charge_state", 1.0))
    soc_clamped = min(max(soc, 0.0), 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_charge"],
        "charge_state": soc_clamped,
    }


def register_unit(state: State) -> dict[str, Any]:
    """Finalizes the battery asset registration."""
    return {
        "log": [f"{UNISPSC_CODE}:register_unit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "voltage": state.get("voltage"),
                "capacity": state.get("capacity_ah"),
                "chemistry": state.get("chemistry"),
                "soc": state.get("charge_state"),
            },
            "compliant": state.get("is_compliant", False),
            "status": "registered" if state.get("is_compliant") else "rejected",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("verify", verify_charge)
_g.add_node("register", register_unit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "register")
_g.add_edge("register", END)

graph = _g.compile()
