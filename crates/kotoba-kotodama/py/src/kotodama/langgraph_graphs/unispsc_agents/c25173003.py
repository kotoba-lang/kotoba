# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173003 — Rail Light (segment 25).

Bespoke logic for technical specification validation, efficiency assessment,
and asset finalization for Rail Light equipment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173003"
UNISPSC_TITLE = "Rail Light"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173003"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    lumens: int
    voltage: float
    mounting_type: str
    efficiency_rating: str
    is_compliant: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Inspects the input for required lighting specifications."""
    inp = state.get("input") or {}
    lumen_val = int(inp.get("lumens", 0))
    volt_val = float(inp.get("voltage", 0.0))
    mount = str(inp.get("mounting", "rail-track"))

    # Requirement: must have positive lumens and voltage
    compliant = lumen_val > 0 and volt_val > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs:compliant={compliant}"],
        "lumens": lumen_val,
        "voltage": volt_val,
        "mounting_type": mount,
        "is_compliant": compliant,
    }


def analyze_efficiency(state: State) -> dict[str, Any]:
    """Calculates efficiency tiers based on lumen output per volt (proxy)."""
    l = state.get("lumens", 0)
    v = state.get("voltage", 1.0)

    ratio = l / v
    tier = "High" if ratio > 100 else "Standard"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_efficiency:tier={tier}"],
        "efficiency_rating": tier,
    }


def finalize_actor(state: State) -> dict[str, Any]:
    """Constructs the final result payload for the Rail Light actor."""
    is_ok = state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_actor:ok={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "lumens": state.get("lumens"),
                "voltage": state.get("voltage"),
                "efficiency": state.get("efficiency_rating"),
                "mounting": state.get("mounting_type"),
            },
            "status": "VALIDATED" if is_ok else "INVALID_SPECS",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("analyze", analyze_efficiency)
_g.add_node("finalize", finalize_actor)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
