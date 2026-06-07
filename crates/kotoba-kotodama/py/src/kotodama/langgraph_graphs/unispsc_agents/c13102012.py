# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102012 — Gas (segment 13).

This bespoke LangGraph agent handles state transitions for Gas procurement
and verification, focusing on composition analysis and pressure safety.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102012"
UNISPSC_TITLE = "Gas"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102012"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for "Gas" (13102012)
    gas_type: str
    purity_percentage: float
    pressure_psi: float
    is_safe: bool


def validate_input(state: State) -> dict[str, Any]:
    """Validates the input gas specifications and type."""
    inp = state.get("input") or {}
    gas_type = inp.get("gas_type", "natural_gas")
    purity = inp.get("purity", 98.5)
    return {
        "log": [f"{UNISPSC_CODE}:validate_input type={gas_type}"],
        "gas_type": gas_type,
        "purity_percentage": purity,
    }


def check_pressure(state: State) -> dict[str, Any]:
    """Monitors the gas pressure for safety compliance."""
    inp = state.get("input") or {}
    pressure = inp.get("pressure", 2150.0)
    # Assume 1500-2500 psi is the safe operating range
    safe = 1500.0 <= pressure <= 2500.0
    return {
        "log": [f"{UNISPSC_CODE}:check_pressure pressure={pressure} psi"],
        "pressure_psi": pressure,
        "is_safe": safe,
    }


def finalize_agent(state: State) -> dict[str, Any]:
    """Finalizes the gas processing agent state and produces result."""
    safe = state.get("is_safe", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_agent safe={safe}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "COMPLIANT" if safe else "NON_COMPLIANT",
            "purity": state.get("purity_percentage", 0.0),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_input", validate_input)
_g.add_node("check_pressure", check_pressure)
_g.add_node("finalize_agent", finalize_agent)

_g.add_edge(START, "validate_input")
_g.add_edge("validate_input", "check_pressure")
_g.add_edge("check_pressure", "finalize_agent")
_g.add_edge("finalize_agent", END)

graph = _g.compile()
