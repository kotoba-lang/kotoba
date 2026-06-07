# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271717 — Flashback (segment 23).
Bespoke implementation for Flashback arrestor safety verification and processing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271717"
UNISPSC_TITLE = "Flashback"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271717"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Flashback Arrestor safety
    gas_type: str
    pressure_rating_psi: float
    thermal_cut_off_active: bool
    integrity_verified: bool


def inspect_safety_device(state: State) -> dict[str, Any]:
    """Inspects the flashback arrestor for basic structural integrity."""
    inp = state.get("input") or {}
    gas = inp.get("gas_type", "Acetylene")
    pressure = float(inp.get("max_pressure", 15.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_safety_device"],
        "gas_type": gas,
        "pressure_rating_psi": pressure,
        "integrity_verified": pressure > 0 and pressure < 100,
    }


def verify_gas_compatibility(state: State) -> dict[str, Any]:
    """Checks if the arrestor is rated for the specific fuel gas in use."""
    gas = state.get("gas_type", "Unknown")
    # Flashback arrestors are gas-specific (e.g., Acetylene vs Oxygen/Propane)
    compatible = gas.lower() in ["acetylene", "hydrogen", "propane", "methane"]

    return {
        "log": [f"{UNISPSC_CODE}:verify_gas_compatibility"],
        "thermal_cut_off_active": compatible,
    }


def issue_safety_report(state: State) -> dict[str, Any]:
    """Finalizes the inspection and issues the compliance report."""
    integrity = state.get("integrity_verified", False)
    compatibility = state.get("thermal_cut_off_active", False)
    ok = integrity and compatibility

    return {
        "log": [f"{UNISPSC_CODE}:issue_safety_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "APPROVED" if ok else "REJECTED",
            "safety_check": {
                "gas": state.get("gas_type"),
                "pressure": state.get("pressure_rating_psi"),
                "integrity": integrity,
                "compatibility": compatibility
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_safety_device)
_g.add_node("verify", verify_gas_compatibility)
_g.add_node("report", issue_safety_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "report")
_g.add_edge("report", END)

graph = _g.compile()
