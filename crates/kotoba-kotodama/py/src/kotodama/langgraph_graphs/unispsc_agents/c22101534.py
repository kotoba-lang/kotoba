# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101534 — Pneumatic (segment 22).

This bespoke agent implements logic for pneumatic system orchestration,
managing pressure thresholds, flow rate requirements, and safety protocols
specific to compressed air machinery and tools.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101534"
UNISPSC_TITLE = "Pneumatic"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101534"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Pneumatic tools
    operating_pressure_psi: int
    flow_rate_cfm: float
    lubrication_required: bool
    safety_valve_active: bool
    hose_id: str


def inspect_parameters(state: State) -> dict[str, Any]:
    """Inspects incoming pneumatic requirements and initializes system state."""
    inp = state.get("input") or {}
    psi = inp.get("psi", 90)
    cfm = inp.get("cfm", 4.5)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_parameters - Pressure: {psi} PSI, Flow: {cfm} CFM"],
        "operating_pressure_psi": psi,
        "flow_rate_cfm": cfm,
        "hose_id": inp.get("hose_id", "ST-001"),
        "lubrication_required": inp.get("need_lube", True),
    }


def validate_safety(state: State) -> dict[str, Any]:
    """Ensures pneumatic pressure is within safe operating limits for the tool."""
    psi = state.get("operating_pressure_psi", 0)
    # Safety logic: most pneumatic tools operate between 70 and 120 PSI
    is_safe = 0 < psi <= 125

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety - Compliance: {is_safe}"],
        "safety_valve_active": not is_safe,
    }


def authorize_operation(state: State) -> dict[str, Any]:
    """Finalizes the pneumatic system configuration and prepares the response."""
    safety_violation = state.get("safety_valve_active", True)
    ready = not safety_violation

    return {
        "log": [f"{UNISPSC_CODE}:authorize_operation - Ready: {ready}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "OPERATIONAL" if ready else "HALTED",
            "telemetry": {
                "psi": state.get("operating_pressure_psi"),
                "cfm": state.get("flow_rate_cfm"),
                "lube": state.get("lubrication_required"),
                "hose": state.get("hose_id")
            },
            "ok": ready,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_parameters", inspect_parameters)
_g.add_node("validate_safety", validate_safety)
_g.add_node("authorize_operation", authorize_operation)

_g.add_edge(START, "inspect_parameters")
_g.add_edge("inspect_parameters", "validate_safety")
_g.add_edge("validate_safety", "authorize_operation")
_g.add_edge("authorize_operation", END)

graph = _g.compile()
