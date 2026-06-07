# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15111506 — Fuel Procurement (segment 15).

Bespoke graph logic for fuel procurement operations, handling supply chain
verification, vendor authorization, and procurement finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15111506"
UNISPSC_TITLE = "Fuel Procurement"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15111506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    fuel_grade: str
    volume_liters: float
    vendor_auth_token: str
    procurement_status: str


def check_requirements(state: State) -> dict[str, Any]:
    """Evaluates the fuel procurement request against standard requirements."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Standard")
    volume = float(inp.get("volume", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:check_requirements"],
        "fuel_grade": grade,
        "volume_liters": volume,
        "procurement_status": "pending_verification"
    }


def authorize_vendor(state: State) -> dict[str, Any]:
    """Simulates vendor authorization for the specific fuel grade and volume."""
    is_valid = state.get("volume_liters", 0) > 0
    token = f"AUTH-{UNISPSC_CODE}-{'VALID' if is_valid else 'FAIL'}"
    return {
        "log": [f"{UNISPSC_CODE}:authorize_vendor"],
        "vendor_auth_token": token,
        "procurement_status": "authorized" if is_valid else "failed_authorization"
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement transaction and sets the result state."""
    authorized = state.get("procurement_status") == "authorized"
    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "fuel_grade": state.get("fuel_grade"),
            "volume": state.get("volume_liters"),
            "auth_token": state.get("vendor_auth_token"),
            "status": state.get("procurement_status"),
            "ok": authorized,
        },
    }


_g = StateGraph(State)
_g.add_node("check_requirements", check_requirements)
_g.add_node("authorize_vendor", authorize_vendor)
_g.add_node("execute_procurement", execute_procurement)

_g.add_edge(START, "check_requirements")
_g.add_edge("check_requirements", "authorize_vendor")
_g.add_edge("authorize_vendor", "execute_procurement")
_g.add_edge("execute_procurement", END)

graph = _g.compile()
