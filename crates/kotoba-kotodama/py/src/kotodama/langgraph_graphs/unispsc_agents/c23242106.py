# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242106 — Tool (segment 23).

Bespoke graph logic for industrial tool lifecycle management, including
inspection, maintenance verification, and operational certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242106"
UNISPSC_TITLE = "Tool"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242106"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for "Tool"
    tool_category: str
    specification_verified: bool
    maintenance_rating: float
    operational_ready: bool


def inspect_tool(state: State) -> dict[str, Any]:
    """
    Analyzes the tool input to determine category and verify baseline specs.
    """
    inp = state.get("input") or {}
    category = inp.get("category", "generic_industrial")
    specs = inp.get("specifications", {})

    # Logic: Verify if required physical dimensions are present
    has_specs = bool(specs.get("dimensions") and specs.get("material"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_tool"],
        "tool_category": category,
        "specification_verified": has_specs,
    }


def verify_maintenance(state: State) -> dict[str, Any]:
    """
    Simulates a check of maintenance logs and wear-and-tear metrics.
    """
    inp = state.get("input") or {}
    usage_hours = inp.get("usage_hours", 0)

    # Logic: Calculate a rating based on usage relative to a 1000hr cycle
    base_rating = 1.0 - (usage_hours / 2000.0)
    final_rating = max(0.0, min(1.0, base_rating))

    return {
        "log": [f"{UNISPSC_CODE}:verify_maintenance"],
        "maintenance_rating": final_rating,
    }


def certify_for_use(state: State) -> dict[str, Any]:
    """
    Final node to certify the tool for industrial operation.
    """
    spec_ok = state.get("specification_verified", False)
    maint_ok = state.get("maintenance_rating", 0) > 0.7

    ready = spec_ok and maint_ok

    return {
        "log": [f"{UNISPSC_CODE}:certify_for_use"],
        "operational_ready": ready,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": "APPROVED" if ready else "REJECTED",
            "metrics": {
                "maintenance_score": state.get("maintenance_rating"),
                "spec_verification": spec_ok
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_tool)
_g.add_node("verify", verify_maintenance)
_g.add_node("certify", certify_for_use)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
