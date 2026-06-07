# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23161514 — Procure (segment 23).

Bespoke graph logic for industrial procurement services. This agent handles
the lifecycle of a procurement requisition, including requisition validation,
supplier tiering, and purchase execution within the manufacturing context.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23161514"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23161514"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Procure
    requisition_id: str
    supplier_tier: int
    inventory_impact: str
    compliance_verified: bool


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request and assigns a requisition ID."""
    inp = state.get("input") or {}
    req_id = inp.get("id", "REQ-TEMP-001")
    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition:{req_id}"],
        "requisition_id": req_id,
        "compliance_verified": "item_code" in inp,
    }


def source_vendor(state: State) -> dict[str, Any]:
    """Determines the appropriate supplier tier based on the requisition scope."""
    # Logic to simulate sourcing from an approved vendor list
    tier = 1 if state.get("compliance_verified") else 3
    return {
        "log": [f"{UNISPSC_CODE}:source_vendor:tier_{tier}"],
        "supplier_tier": tier,
        "inventory_impact": "high" if tier == 1 else "low",
    }


def execute_purchase(state: State) -> dict[str, Any]:
    """Finalizes the procurement process and generates the result artifact."""
    req_id = state.get("requisition_id")
    tier = state.get("supplier_tier")

    return {
        "log": [f"{UNISPSC_CODE}:execute_purchase:complete"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_status": "executed",
            "details": {
                "requisition": req_id,
                "tier": tier,
                "impact": state.get("inventory_impact")
            },
            "ok": state.get("compliance_verified", False),
        },
    }


_g = StateGraph(State)

_g.add_node("validate_requisition", validate_requisition)
_g.add_node("source_vendor", source_vendor)
_g.add_node("execute_purchase", execute_purchase)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "source_vendor")
_g.add_edge("source_vendor", "execute_purchase")
_g.add_edge("execute_purchase", END)

graph = _g.compile()
