# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12171500 — Chemical Procurement (segment 12).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12171500"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12171500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    sds_verified: bool
    hazard_classification: str
    procurement_id: str
    approval_status: str


def scrub_request(state: State) -> dict[str, Any]:
    """Validate input and check for SDS (Safety Data Sheet) presence."""
    inp = state.get("input") or {}
    sds_ref = inp.get("sds_reference")
    return {
        "log": [f"{UNISPSC_CODE}:scrub_request"],
        "sds_verified": bool(sds_ref),
        "procurement_id": inp.get("id", "REQ-TEMP"),
    }


def analyze_hazards(state: State) -> dict[str, Any]:
    """Assess hazard level and set internal classification based on description."""
    inp = state.get("input") or {}
    desc = str(inp.get("description", "")).lower()
    h_class = "Standard"

    # Simple heuristic for chemical hazard assessment
    if any(term in desc for term in ["reactive", "toxic", "acid", "volatile"]):
        h_class = "Hazardous"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_hazards"],
        "hazard_classification": h_class,
    }


def approve_procurement(state: State) -> dict[str, Any]:
    """Finalize status based on compliance and hazards."""
    h_class = state.get("hazard_classification", "Standard")
    sds_ok = state.get("sds_verified", False)

    status = "Approved"
    if h_class == "Hazardous" and not sds_ok:
        status = "Flagged: Missing SDS"
    elif not sds_ok:
        status = "Pending Verification"

    return {
        "log": [f"{UNISPSC_CODE}:approve_procurement"],
        "approval_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": state.get("procurement_id"),
            "status": status,
            "hazard_level": h_class,
            "ok": status == "Approved",
        },
    }


_g = StateGraph(State)
_g.add_node("scrub_request", scrub_request)
_g.add_node("analyze_hazards", analyze_hazards)
_g.add_node("approve_procurement", approve_procurement)

_g.add_edge(START, "scrub_request")
_g.add_edge("scrub_request", "analyze_hazards")
_g.add_edge("analyze_hazards", "approve_procurement")
_g.add_edge("approve_procurement", END)

graph = _g.compile()
