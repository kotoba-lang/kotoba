# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10121703 — Chickens (segment 10).

Bespoke graph logic for live poultry management, specifically handling
the intake, health verification, and logistical registration of livestock.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10121703"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10121703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    breed: str
    flock_count: int
    health_status: str
    quarantine_required: bool


def intake(state: State) -> dict[str, Any]:
    """Node to parse input and initialize flock metadata."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:intake"],
        "breed": inp.get("breed", "White Leghorn"),
        "flock_count": int(inp.get("count", 0)),
    }


def health_check(state: State) -> dict[str, Any]:
    """Node to verify health status and determine quarantine needs."""
    count = state.get("flock_count", 0)
    # Simple logic: large flocks require mandatory quarantine for safety
    needs_quarantine = count > 100
    return {
        "log": [f"{UNISPSC_CODE}:health_check"],
        "health_status": "verified" if count > 0 else "pending",
        "quarantine_required": needs_quarantine,
    }


def register(state: State) -> dict[str, Any]:
    """Node to finalize the registration of the poultry lot."""
    return {
        "log": [f"{UNISPSC_CODE}:register"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "data": {
                "breed": state.get("breed"),
                "count": state.get("flock_count"),
                "health": state.get("health_status"),
                "quarantine": state.get("quarantine_required"),
            },
            "success": True,
        },
    }


_g = StateGraph(State)

_g.add_node("intake", intake)
_g.add_node("health_check", health_check)
_g.add_node("register", register)

_g.add_edge(START, "intake")
_g.add_edge("intake", "health_check")
_g.add_edge("health_check", "register")
_g.add_edge("register", END)

graph = _g.compile()
