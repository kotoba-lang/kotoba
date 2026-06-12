# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13101721 — Ceramic Procurement (segment 13).

This module implements a bespoke LangGraph for ceramic material procurement,
handling specification validation, supply chain evaluation, and execution logic.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13101721"
UNISPSC_TITLE = "Ceramic Procurement"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13101721"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Bespoke domain fields for Ceramic Procurement
    ceramic_type: str
    quantity_kg: float
    firing_temp_celsius: int
    quality_cert_required: bool
    vendor_tier: str


def validate_ceramic_specs(state: State) -> dict[str, Any]:
    """Validates the material specifications for ceramic procurement."""
    inp = state.get("input") or {}
    c_type = inp.get("ceramic_type", "kaolin-base")
    qty = float(inp.get("qty", 500.0))
    temp = int(inp.get("firing_temp", 1250))

    return {
        "log": [f"{UNISPSC_CODE}:validate_ceramic_specs"],
        "ceramic_type": c_type,
        "quantity_kg": qty,
        "firing_temp_celsius": temp,
        "quality_cert_required": temp > 1100
    }


def evaluate_supply_chain(state: State) -> dict[str, Any]:
    """Determines vendor tiering based on material requirements."""
    temp = state.get("firing_temp_celsius", 0)
    tier = "Tier-1" if temp > 1200 else "Tier-2"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_supply_chain"],
        "vendor_tier": tier
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement process for ceramic materials."""
    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ceramic_type": state.get("ceramic_type"),
            "vendor_tier": state.get("vendor_tier"),
            "certified": state.get("quality_cert_required"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_ceramic_specs)
_g.add_node("evaluate", evaluate_supply_chain)
_g.add_node("execute", execute_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "evaluate")
_g.add_edge("evaluate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
