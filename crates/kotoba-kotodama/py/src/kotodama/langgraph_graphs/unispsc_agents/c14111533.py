# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111533 — Paper Procurement (segment 14).

Bespoke graph for paper procurement lifecycle management, including
sustainability verification, supplier tiering, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111533"
UNISPSC_TITLE = "Paper Procurement"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111533"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    paper_spec: str
    quantity_reams: int
    is_fsc_certified: bool
    supplier_tier: int
    audit_status: str


def validate_procurement_request(state: State) -> dict[str, Any]:
    """Extracts procurement details and initializes state."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:validate_procurement_request"],
        "paper_spec": inp.get("paper_spec", "recycled-office-a4"),
        "quantity_reams": int(inp.get("quantity", 10)),
        "is_fsc_certified": bool(inp.get("fsc_certified", True)),
        "supplier_tier": int(inp.get("supplier_tier", 1)),
    }


def evaluate_sustainability(state: State) -> dict[str, Any]:
    """Checks FSC certification and supplier ranking."""
    certified = state.get("is_fsc_certified", False)
    tier = state.get("supplier_tier", 3)

    # Priority given to FSC certified suppliers in top tiers
    if certified and tier <= 2:
        status = "green-listed"
    elif certified:
        status = "standard-approval"
    else:
        status = "audit-required"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_sustainability"],
        "audit_status": status,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final procurement record and status."""
    status = state.get("audit_status", "pending")
    spec = state.get("paper_spec")
    qty = state.get("quantity_reams")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "audit": status,
            "summary": f"Ordered {qty} reams of {spec}",
            "ok": status != "audit-required",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_procurement_request)
_g.add_node("evaluate", evaluate_sustainability)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
