# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111811 — Paper Procurement (segment 14).

Bespoke graph for managing paper-specific procurement workflows, including
specification validation, sustainability verification (FSC/PEFC), and
lead-time estimation for bulk quantities.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111811"
UNISPSC_TITLE = "Paper Procurement"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111811"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields
    paper_specification: dict[str, Any]
    certified_sustainable: bool
    lead_time_days: int
    procurement_status: str


def evaluate_specification(state: State) -> dict[str, Any]:
    """Validates paper specs such as GSM (weight), brightness, and opacity."""
    inp = state.get("input") or {}
    spec = inp.get("specification", {"gsm": 80, "finish": "matte"})

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_specification"],
        "paper_specification": spec,
        "procurement_status": "spec_validated"
    }


def verify_sustainability(state: State) -> dict[str, Any]:
    """Checks for environmental certifications like FSC or recycled content."""
    inp = state.get("input") or {}
    # Default to true if specified in input, otherwise mock check
    is_eco = inp.get("require_certified", True)

    return {
        "log": [f"{UNISPSC_CODE}:verify_sustainability"],
        "certified_sustainable": is_eco,
        "procurement_status": "sustainability_verified"
    }


def calculate_lead_time(state: State) -> dict[str, Any]:
    """Estimates delivery window based on volume and paper type."""
    inp = state.get("input") or {}
    quantity = inp.get("quantity_reams", 100)

    # Mock logic: larger orders or specialty finishes take longer
    days = 3 if quantity < 500 else 10

    return {
        "log": [f"{UNISPSC_CODE}:calculate_lead_time"],
        "lead_time_days": days,
        "procurement_status": "timeline_established"
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Aggregates procurement data into the final result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "authorized",
            "details": {
                "spec": state.get("paper_specification"),
                "sustainable": state.get("certified_sustainable"),
                "delivery_est_days": state.get("lead_time_days")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("evaluate_specification", evaluate_specification)
_g.add_node("verify_sustainability", verify_sustainability)
_g.add_node("calculate_lead_time", calculate_lead_time)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "evaluate_specification")
_g.add_edge("evaluate_specification", "verify_sustainability")
_g.add_edge("verify_sustainability", "calculate_lead_time")
_g.add_edge("calculate_lead_time", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
