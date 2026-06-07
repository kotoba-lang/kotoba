# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102020 — Catalyst.
Handles state transitions for chemical catalytic process verification and optimization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102020"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102020"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Catalyst domain state
    catalyst_type: str
    activation_temp_c: float
    purity_ratio: float
    is_safe: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the input specification for the catalyst batch."""
    inp = state.get("input") or {}
    c_type = inp.get("type", "transition_metal")
    purity = float(inp.get("purity", 0.99))
    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "catalyst_type": c_type,
        "purity_ratio": purity,
        "is_safe": purity > 0.90,
    }


def compute_activation(state: State) -> dict[str, Any]:
    """Calculates the thermal activation requirements for the catalyst."""
    c_type = state.get("catalyst_type", "unknown")
    # Logic: metal catalysts require higher temps than organic ones
    base_temp = 450.0 if "metal" in c_type.lower() else 120.0
    return {
        "log": [f"{UNISPSC_CODE}:compute_activation"],
        "activation_temp_c": base_temp,
    }


def emit_catalyst_data(state: State) -> dict[str, Any]:
    """Packages the catalytic metadata and emits the final state."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_catalyst_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "catalyst_type": state.get("catalyst_type"),
            "activation_temp": state.get("activation_temp_c"),
            "purity": state.get("purity_ratio"),
            "status": "certified" if state.get("is_safe") else "rejected",
            "ok": state.get("is_safe", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_spec)
_g.add_node("compute", compute_activation)
_g.add_node("emit", emit_catalyst_data)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
