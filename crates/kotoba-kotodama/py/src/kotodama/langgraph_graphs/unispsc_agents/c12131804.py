# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12131804 — Procure (segment 12).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12131804"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12131804"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Procurement
    procurement_mode: str
    vendor_vetted: bool
    budget_limit: float
    approval_path: list[str]


def analyze_requisition(state: State) -> dict[str, Any]:
    """Analyzes the incoming procurement request and determines constraints."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "standard")
    limit = float(inp.get("budget", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:analyze_requisition"],
        "procurement_mode": mode,
        "budget_limit": limit,
        "approval_path": ["received"],
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks vendor status and budget alignment."""
    mode = state.get("procurement_mode")
    budget = state.get("budget_limit", 0.0)
    # Simulation: Express mode or small budgets are automatically vetted
    vetted = mode == "express" or budget < 2500.0
    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "vendor_vetted": vetted,
        "approval_path": ["compliance_checked"],
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and emits the result."""
    vetted = state.get("vendor_vetted", False)
    mode = state.get("procurement_mode")
    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "AUTHORIZED" if vetted else "PENDING_APPROVAL",
            "applied_mode": mode,
            "path": state.get("approval_path", []) + ["finalized"],
            "ok": vetted,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_requisition)
_g.add_node("verify", verify_compliance)
_g.add_node("execute", execute_procurement)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
