# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172109 — Airbag (segment 25).

Bespoke graph logic for Airbag lifecycle management, including safety
verification, deployment telemetry, and serial number tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172109"
UNISPSC_TITLE = "Airbag"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172109"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Airbag lifecycle
    serial_number: str
    inflation_pressure_psi: float
    initiator_continuity: bool
    is_safety_certified: bool


def verify_canister(state: State) -> dict[str, Any]:
    """Validate the gas generator canister serial and integrity."""
    inp = state.get("input") or {}
    sn = inp.get("serial_number", "SN-AB-000")
    return {
        "log": [f"{UNISPSC_CODE}:verify_canister:{sn}"],
        "serial_number": sn,
        "initiator_continuity": True if inp.get("continuity") != "FAIL" else False,
    }


def pressure_check(state: State) -> dict[str, Any]:
    """Perform a simulated pressure sensor and seal test."""
    continuity = state.get("initiator_continuity", False)
    pressure = 3000.0 if continuity else 0.0
    return {
        "log": [f"{UNISPSC_CODE}:pressure_check: {pressure}psi"],
        "inflation_pressure_psi": pressure,
        "is_safety_certified": continuity and pressure > 2500,
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Finalize the airbag assembly certification record."""
    certified = state.get("is_safety_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "serial": state.get("serial_number"),
            "status": "READY" if certified else "DEFECTIVE",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("verify", verify_canister)
_g.add_node("pressure", pressure_check)
_g.add_node("finalize", finalize_asset)

_g.add_edge(START, "verify")
_g.add_edge("verify", "pressure")
_g.add_edge("pressure", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
