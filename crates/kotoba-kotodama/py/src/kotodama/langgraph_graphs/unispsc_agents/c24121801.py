# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24121801 — Aerosol (segment 24).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24121801"
UNISPSC_TITLE = "Aerosol"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24121801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Aerosol conditioning and packaging
    pressure_psi: float
    propellant_type: str
    nozzle_functional: bool
    voc_content_pct: float
    batch_status: str


def inspect_canister(state: State) -> dict[str, Any]:
    """Inspects the physical integrity and internal pressure of the aerosol canister."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure_psi", 48.5))
    nozzle = bool(inp.get("nozzle_test", True))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_canister"],
        "pressure_psi": pressure,
        "nozzle_functional": nozzle,
    }


def verify_chemistry(state: State) -> dict[str, Any]:
    """Verifies the propellant type and Volatile Organic Compound (VOC) compliance."""
    inp = state.get("input") or {}
    propellant = str(inp.get("propellant", "Nitrogen"))
    voc = float(inp.get("voc_level", 4.2))
    return {
        "log": [f"{UNISPSC_CODE}:verify_chemistry"],
        "propellant_type": propellant,
        "voc_content_pct": voc,
    }


def certify_unit(state: State) -> dict[str, Any]:
    """Performs final quality assurance and generates the certification result."""
    pressure = state.get("pressure_psi", 0)
    voc = state.get("voc_content_pct", 100)
    nozzle = state.get("nozzle_functional", False)

    # Simple compliance logic: safe pressure range and low VOCs
    is_compliant = (30.0 <= pressure <= 95.0) and (voc < 10.0) and nozzle
    status = "CERTIFIED" if is_compliant else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_unit"],
        "batch_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_compliant,
            "status": status,
            "telemetry": {
                "p_psi": pressure,
                "voc_pct": voc,
                "propellant": state.get("propellant_type"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_canister", inspect_canister)
_g.add_node("verify_chemistry", verify_chemistry)
_g.add_node("certify_unit", certify_unit)

_g.add_edge(START, "inspect_canister")
_g.add_edge("inspect_canister", "verify_chemistry")
_g.add_edge("verify_chemistry", "certify_unit")
_g.add_edge("certify_unit", END)

graph = _g.compile()
