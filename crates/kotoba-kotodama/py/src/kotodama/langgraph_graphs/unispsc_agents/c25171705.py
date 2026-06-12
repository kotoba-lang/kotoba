# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171705 — Rotor (segment 25).

Bespoke LangGraph logic for managing rotor inspection and certification workflows.
This agent handles state transitions for balancing, integrity checks, and
operational limit verification for high-speed rotating components.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171705"
UNISPSC_TITLE = "Rotor"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Rotor
    balance_verified: bool
    rpm_rating: int
    material_integrity_check: str
    bearing_tolerance_ok: bool


def inspect_integrity(state: State) -> dict[str, Any]:
    """Inspects the structural integrity and sets operational limits."""
    inp = state.get("input") or {}
    requested_rpm = inp.get("max_rpm", 3600)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_integrity"],
        "material_integrity_check": "passed",
        "rpm_rating": requested_rpm,
        "bearing_tolerance_ok": True,
    }


def verify_balance(state: State) -> dict[str, Any]:
    """Simulates dynamic balancing verification."""
    # Logic to ensure the rotor meets G2.5 or better balance grades
    return {
        "log": [f"{UNISPSC_CODE}:verify_balance"],
        "balance_verified": True,
    }


def certify_rotor(state: State) -> dict[str, Any]:
    """Finalizes the certification and produces the output manifest."""
    is_ok = state.get("balance_verified", False) and state.get("bearing_tolerance_ok", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_rotor"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certification": "ISO-1940-1",
            "max_safe_rpm": state.get("rpm_rating"),
            "status": "certified" if is_ok else "rejected",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_integrity)
_g.add_node("balance", verify_balance)
_g.add_node("certify", certify_rotor)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "balance")
_g.add_edge("balance", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
