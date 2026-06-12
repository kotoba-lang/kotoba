# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10161501 — Fertilizer (segment 10).

This bespoke agent implements a domain-specific workflow for fertilizer
specification analysis, regulatory compliance verification, and application
instruction generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161501"
UNISPSC_TITLE = "Fertilizer"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Fertilizer
    nutrient_analysis: dict[str, float]
    batch_safety_status: str
    compliance_id: str
    recommended_application_rate: str


def evaluate_nutrient_profile(state: State) -> dict[str, Any]:
    """Analyzes requested N-P-K (Nitrogen, Phosphorus, Potassium) ratios."""
    inp = state.get("input") or {}
    # Default to a balanced 10-10-10 if not provided
    target = inp.get("target_npk", {"N": 10.0, "P": 10.0, "K": 10.0})
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_nutrient_profile"],
        "nutrient_analysis": target,
        "batch_safety_status": "PENDING"
    }


def verify_regulatory_compliance(state: State) -> dict[str, Any]:
    """Checks fertilizer composition against environmental safety standards."""
    analysis = state.get("nutrient_analysis", {})
    # Simulation: Nitrogen levels above 30% require specialized handling permits
    nitrogen_level = analysis.get("N", 0.0)
    permit_required = nitrogen_level > 30.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_regulatory_compliance"],
        "batch_safety_status": "PASSED",
        "compliance_id": f"ENV-{UNISPSC_CODE}-{'PRMT' if permit_required else 'STD'}",
        "recommended_application_rate": "5 lbs per 1000 sq ft" if not permit_required else "3 lbs per 1000 sq ft (High Nitrate)"
    }


def emit_product_manifest(state: State) -> dict[str, Any]:
    """Generates the final certification and dispatch result."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_product_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "CERTIFIED",
            "compliance": state.get("compliance_id"),
            "safety": state.get("batch_safety_status"),
            "analysis": state.get("nutrient_analysis"),
            "application": state.get("recommended_application_rate")
        },
    }


_g = StateGraph(State)

_g.add_node("evaluate", evaluate_nutrient_profile)
_g.add_node("verify", verify_regulatory_compliance)
_g.add_node("emit", emit_product_manifest)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
