# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23281800 — Procure (segment 23).
Bespoke implementation for industrial and commercial procurement services.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23281800"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23281800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Procurement
    procurement_id: str
    vendor_selection: str
    budget_allocated: float
    contract_signed: bool
    delivery_terms: str


def identify_requirement(state: State) -> dict[str, Any]:
    """Identify and validate the procurement requirement."""
    inp = state.get("input") or {}
    p_id = str(inp.get("id", "PROC-DEFAULT"))
    return {
        "log": [f"{UNISPSC_CODE}:identify_requirement"],
        "procurement_id": p_id,
        "delivery_terms": str(inp.get("terms", "FOB Destination")),
    }


def source_vendor(state: State) -> dict[str, Any]:
    """Simulate vendor sourcing and selection logic for industrial services."""
    return {
        "log": [f"{UNISPSC_CODE}:source_vendor"],
        "vendor_selection": "Industrial Supply Network",
        "budget_allocated": 25000.0,
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Finalize the procurement order and set the result dictionary."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_order"],
        "contract_signed": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "procurement_id": state.get("procurement_id"),
            "vendor": state.get("vendor_selection"),
            "budget": state.get("budget_allocated"),
            "status": "APPROVED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("identify", identify_requirement)
_g.add_node("source", source_vendor)
_g.add_node("finalize", finalize_order)

_g.add_edge(START, "identify")
_g.add_edge("identify", "source")
_g.add_edge("source", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
