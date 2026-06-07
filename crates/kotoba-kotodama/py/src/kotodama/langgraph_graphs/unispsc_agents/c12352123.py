# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352123 — Catalyst (segment 12).

Bespoke graph for managing chemical catalyst state transitions, reaction
validation, and batch verification. This agent simulates the lifecycle of
a catalyst within a production workflow.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352123"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352123"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Catalyst
    reaction_type: str
    purity_threshold: float
    batch_serial: str
    is_activated: bool


def validate_catalyst(state: State) -> dict[str, Any]:
    """Validates the input parameters for the catalyst batch."""
    inp = state.get("input") or {}
    batch_serial = inp.get("batch_serial", "CAT-DEFAULT-001")
    reaction_type = inp.get("reaction_type", "hydrogenation")

    return {
        "log": [f"{UNISPSC_CODE}:validate_catalyst -> {batch_serial}"],
        "batch_serial": batch_serial,
        "reaction_type": reaction_type,
        "is_activated": False,
    }


def process_activation(state: State) -> dict[str, Any]:
    """Simulates the physical activation of the catalyst material."""
    # Mock purity calculation based on reaction type
    rtype = state.get("reaction_type", "unknown")
    purity = 0.995 if rtype == "hydrogenation" else 0.980

    return {
        "log": [f"{UNISPSC_CODE}:process_activation -> {rtype}"],
        "purity_threshold": purity,
        "is_activated": True,
    }


def finalize_catalyst_state(state: State) -> dict[str, Any]:
    """Confirms compliance and emits the final catalyst agent state."""
    purity = state.get("purity_threshold", 0.0)
    serial = state.get("batch_serial", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalyst_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_serial": serial,
            "purity_level": purity,
            "status": "ready_for_dispatch",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_catalyst)
_g.add_node("activate", process_activation)
_g.add_node("finalize", finalize_catalyst_state)

_g.add_edge(START, "validate")
_g.add_edge("validate", "activate")
_g.add_edge("activate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
