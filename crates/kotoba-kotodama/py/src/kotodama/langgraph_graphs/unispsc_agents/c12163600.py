# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12163600 — Gas (segment 12).

Bespoke graph logic for gas resource management, handling pressure analysis,
flow regulation, and safety verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12163600"
UNISPSC_TITLE = "Gas"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12163600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    gas_type: str
    pressure_psi: float
    flow_rate_m3h: float
    safety_seal_verified: bool


def analyze_source(state: State) -> dict[str, Any]:
    """Inspects the input for gas characteristics and initial pressure state."""
    inp = state.get("input") or {}
    g_type = str(inp.get("gas_type", "Natural Gas"))
    psi = float(inp.get("pressure_psi", 2.5))
    return {
        "log": [f"{UNISPSC_CODE}:analyze_source - type: {g_type}, pressure: {psi} PSI"],
        "gas_type": g_type,
        "pressure_psi": psi,
    }


def regulate_flow(state: State) -> dict[str, Any]:
    """Calculates flow rate based on pressure and verifies safety thresholds."""
    psi = state.get("pressure_psi", 0.0)
    # Define safety operating range (0.5 to 15.0 PSI)
    is_safe = 0.5 <= psi <= 15.0
    # Flow rate is a function of pressure if safety conditions are met
    flow = 42.5 * (psi / 2.0) if is_safe else 0.0
    return {
        "log": [f"{UNISPSC_CODE}:regulate_flow - flow: {flow:.2f} m3/h, safe: {is_safe}"],
        "flow_rate_m3h": flow,
        "safety_seal_verified": is_safe,
    }


def finalize_transaction(state: State) -> dict[str, Any]:
    """Constructs the final result based on processed state and safety status."""
    is_ok = state.get("safety_seal_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_transaction - status: {'Verified' if is_ok else 'Rejected'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "composition": state.get("gas_type"),
            "throughput": state.get("flow_rate_m3h"),
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_source", analyze_source)
_g.add_node("regulate_flow", regulate_flow)
_g.add_node("finalize_transaction", finalize_transaction)

_g.add_edge(START, "analyze_source")
_g.add_edge("analyze_source", "regulate_flow")
_g.add_edge("regulate_flow", "finalize_transaction")
_g.add_edge("finalize_transaction", END)

graph = _g.compile()
