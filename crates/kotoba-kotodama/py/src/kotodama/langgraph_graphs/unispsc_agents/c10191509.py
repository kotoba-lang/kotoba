# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10191509 — Mining (segment 10).

Bespoke graph logic for mining resource management and extraction workflow.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10191509"
UNISPSC_TITLE = "Mining"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10191509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    extraction_permit_id: str
    ore_quality_score: float
    safety_protocol_active: bool
    yield_estimate: float


def assess_safety(state: State) -> dict[str, Any]:
    """Validates the extraction permit and checks if safety protocols are active."""
    inp = state.get("input") or {}
    permit = inp.get("permit_id", "PENDING")
    safety_ok = inp.get("safety_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:assess_safety - Permit: {permit}"],
        "extraction_permit_id": permit,
        "safety_protocol_active": safety_ok,
    }


def evaluate_yield(state: State) -> dict[str, Any]:
    """Calculates the estimated yield based on ore quality index if safety is verified."""
    if not state.get("safety_protocol_active"):
        return {"log": [f"{UNISPSC_CODE}:evaluate_yield - Safety check failed, skipping yield eval"]}

    inp = state.get("input") or {}
    quality = float(inp.get("quality_index", 0.5))
    est_yield = quality * 1000.0
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_yield - Est Yield: {est_yield}"],
        "ore_quality_score": quality,
        "yield_estimate": est_yield,
    }


def register_extraction(state: State) -> dict[str, Any]:
    """Finalizes the mining request and emits the extraction registration result."""
    permit = state.get("extraction_permit_id")
    is_safe = state.get("safety_protocol_active", False)
    yield_val = state.get("yield_estimate", 0.0)

    success = is_safe and yield_val > 0
    return {
        "log": [f"{UNISPSC_CODE}:register_extraction - Result: {'Success' if success else 'Failed'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "permit": permit,
            "yield": yield_val,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("assess_safety", assess_safety)
_g.add_node("evaluate_yield", evaluate_yield)
_g.add_node("register_extraction", register_extraction)

_g.add_edge(START, "assess_safety")
_g.add_edge("assess_safety", "evaluate_yield")
_g.add_edge("evaluate_yield", "register_extraction")
_g.add_edge("register_extraction", END)

graph = _g.compile()
