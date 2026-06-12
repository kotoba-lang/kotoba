# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122329 — Robot Procurement (segment 20).

Bespoke graph logic for procurement workflows involving robotic systems,
industrial automation components, and specialized sourcing protocols.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122329"
UNISPSC_TITLE = "Robot Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122329"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    specification_verified: bool
    vendor_shortlist: list[str]
    compliance_score: float
    procurement_id: str


def verify_specifications(state: State) -> dict[str, Any]:
    """Verify that the robot specifications meet the procurement requirements."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})

    # Simulate rigorous spec verification (payload, DOF, reach, repeatability)
    verified = bool(specs and specs.get("payload_kg", 0) > 0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications:success={verified}"],
        "specification_verified": verified,
        "compliance_score": 0.95 if verified else 0.0,
    }


def source_vendors(state: State) -> dict[str, Any]:
    """Identify qualified vendors for the specified robotic equipment."""
    if not state.get("specification_verified"):
        return {"log": [f"{UNISPSC_CODE}:source_vendors:aborted_missing_specs"]}

    # Simulate sourcing from a pre-approved robotic vendor database
    shortlist = ["RoboCorp Global", "Precision Motion Dynamics", "AutoFlex Systems"]

    return {
        "log": [f"{UNISPSC_CODE}:source_vendors:shortlisted={len(shortlist)}"],
        "vendor_shortlist": shortlist,
    }


def finalize_procurement_request(state: State) -> dict[str, Any]:
    """Generate the final procurement tender or purchase request."""
    shortlist = state.get("vendor_shortlist") or []
    score = state.get("compliance_score", 0.0)
    p_id = f"PRQ-{UNISPSC_CODE}-2026-B"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_request"],
        "procurement_id": p_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": p_id,
            "eligible_vendors": shortlist,
            "compliance_rating": score,
            "ok": bool(shortlist and score > 0.5),
        },
    }


_g = StateGraph(State)

_g.add_node("verify", verify_specifications)
_g.add_node("source", source_vendors)
_g.add_node("finalize", finalize_procurement_request)

_g.add_edge(START, "verify")
_g.add_edge("verify", "source")
_g.add_edge("source", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
