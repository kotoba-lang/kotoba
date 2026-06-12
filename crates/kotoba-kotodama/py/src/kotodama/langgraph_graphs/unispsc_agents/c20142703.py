# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142703"
UNISPSC_TITLE = "Gas Reg"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    gas_medium: str
    inlet_psi: float
    outlet_psi: float
    diaphragm_intact: bool
    flow_rate_scfh: float


def inspect_hardware(state: State) -> dict[str, Any]:
    """Node: Verify physical integrity and gas medium."""
    inp = state.get("input") or {}
    medium = inp.get("gas", "Nitrogen")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_hardware"],
        "gas_medium": medium,
        "diaphragm_intact": True,
    }


def configure_pressure(state: State) -> dict[str, Any]:
    """Node: Set inlet and target outlet pressure levels."""
    inp = state.get("input") or {}
    inlet = float(inp.get("inlet", 200.0))
    outlet = float(inp.get("outlet", 50.0))
    return {
        "log": [f"{UNISPSC_CODE}:configure_pressure"],
        "inlet_psi": inlet,
        "outlet_psi": outlet,
    }


def verify_flow_capacity(state: State) -> dict[str, Any]:
    """Node: Calculate and verify flow rate and finalize certification."""
    outlet = state.get("outlet_psi", 0.0)
    # Simulated SCFH (Standard Cubic Feet per Hour) calculation
    flow = outlet * 2.45
    return {
        "log": [f"{UNISPSC_CODE}:verify_flow_capacity"],
        "flow_rate_scfh": flow,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "medium": state.get("gas_medium"),
            "flow_scfh": flow,
            "status": "OPERATIONAL" if state.get("diaphragm_intact") else "FAULT",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_hardware)
_g.add_node("configure", configure_pressure)
_g.add_node("verify", verify_flow_capacity)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "configure")
_g.add_edge("configure", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
