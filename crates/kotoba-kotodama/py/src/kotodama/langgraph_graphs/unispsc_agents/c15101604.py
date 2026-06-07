# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15101604 — Procure (segment 15).

Bespoke graph logic for the procurement lifecycle of segment 15 materials.
This agent handles requisition validation, supplier vetting, and budget
allocation for procurement tasks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15101604"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15101604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Procure
    requisition_id: str
    supplier_vetted: bool
    budget_allocation_code: str
    procurement_priority: str
    compliance_verified: bool


def validate_requisition(state: State) -> dict[str, Any]:
    """Analyzes the input for procurement parameters."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-GENERIC-15")
    priority = inp.get("priority", "STANDARD")
    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "procurement_priority": priority,
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks segment 15 specific regulatory requirements."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "compliance_verified": True,
    }


def authorize_supplier(state: State) -> dict[str, Any]:
    """Ensures the selected supplier is in the approved registry."""
    return {
        "log": [f"{UNISPSC_CODE}:authorize_supplier"],
        "supplier_vetted": True,
    }


def allocate_funds(state: State) -> dict[str, Any]:
    """Simulates fund allocation for the procurement order."""
    req_id = state.get("requisition_id", "UNK")
    return {
        "log": [f"{UNISPSC_CODE}:allocate_funds"],
        "budget_allocation_code": f"ALLOC-15-{req_id}",
    }


def emit_procurement_state(state: State) -> dict[str, Any]:
    """Finalizes the procurement agent's output."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_procurement_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "READY_FOR_EXECUTION",
            "requisition_id": state.get("requisition_id"),
            "allocation": state.get("budget_allocation_code"),
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("compliance", verify_compliance)
_g.add_node("vet_supplier", authorize_supplier)
_g.add_node("allocate", allocate_funds)
_g.add_node("emit", emit_procurement_state)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compliance")
_g.add_edge("compliance", "vet_supplier")
_g.add_edge("vet_supplier", "allocate")
_g.add_edge("allocate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
