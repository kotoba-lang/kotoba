# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15101504 — Iron Ore (segment 15).

Bespoke graph logic for iron ore assaying and classification. This agent
handles state transitions for bulk mineral quality verification,
grading iron content, and certifying batches for transport.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15101504"
UNISPSC_TITLE = "Iron Ore"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15101504"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Iron Ore
    iron_content_pct: float
    moisture_content: float
    impurity_profile: dict[str, float]
    grade_tier: str
    is_certified: bool


def validate_assay(state: State) -> dict[str, Any]:
    """Inspects the incoming assay data for mandatory mineral metrics."""
    inp = state.get("input") or {}
    assay = inp.get("assay", {})

    fe = float(assay.get("Fe", 0.0))
    moisture = float(assay.get("moisture", 0.0))
    impurities = {
        "SiO2": float(assay.get("SiO2", 0.0)),
        "Al2O3": float(assay.get("Al2O3", 0.0)),
        "P": float(assay.get("P", 0.0)),
        "S": float(assay.get("S", 0.0)),
    }

    return {
        "log": [f"{UNISPSC_CODE}:validate_assay: Fe={fe}%"],
        "iron_content_pct": fe,
        "moisture_content": moisture,
        "impurity_profile": impurities,
    }


def evaluate_grade(state: State) -> dict[str, Any]:
    """Determines the commercial grade based on iron concentration."""
    fe = state.get("iron_content_pct", 0.0)

    if fe >= 65.0:
        tier = "High Grade (Premium)"
    elif fe >= 62.0:
        tier = "Standard Grade"
    elif fe >= 58.0:
        tier = "Low Grade"
    else:
        tier = "Sub-economic / Rejection"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_grade: classification={tier}"],
        "grade_tier": tier,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Finalizes the state and prepares the actor's certified result."""
    tier = state.get("grade_tier", "Unknown")
    fe = state.get("iron_content_pct", 0.0)

    is_valid = fe > 0 and tier != "Sub-economic / Rejection"

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch: certified={is_valid}"],
        "is_certified": is_valid,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "assay_summary": {
                "fe_pct": fe,
                "tier": tier,
                "moisture": state.get("moisture_content"),
            },
            "status": "APPROVED" if is_valid else "REJECTED",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_assay", validate_assay)
_g.add_node("evaluate_grade", evaluate_grade)
_g.add_node("certify_batch", certify_batch)

_g.add_edge(START, "validate_assay")
_g.add_edge("validate_assay", "evaluate_grade")
_g.add_edge("evaluate_grade", "certify_batch")
_g.add_edge("certify_batch", END)

graph = _g.compile()
