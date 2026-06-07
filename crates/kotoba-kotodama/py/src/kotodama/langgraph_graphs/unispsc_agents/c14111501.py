# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111501 — Paper Procurement (segment 14).

Bespoke graph logic for paper specification validation, inventory checking,
and procurement finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111501"
UNISPSC_TITLE = "Paper Procurement"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields
    paper_type: str
    gsm_weight: int
    recycled_content_pct: int
    availability_status: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the requested paper specifications from input."""
    inp = state.get("input") or {}
    p_type = inp.get("paper_type", "standard_bond")
    gsm = inp.get("gsm_weight", 80)
    recycled = inp.get("recycled_content_pct", 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "paper_type": p_type,
        "gsm_weight": gsm,
        "recycled_content_pct": recycled,
    }


def check_inventory(state: State) -> dict[str, Any]:
    """Simulates inventory availability check for the specified paper weight."""
    gsm = state.get("gsm_weight", 0)
    # Simple logic: heavier specialty papers are 'backordered', lighter are 'in_stock'
    status = "in_stock" if gsm <= 200 else "backordered"

    return {
        "log": [f"{UNISPSC_CODE}:check_inventory"],
        "availability_status": status,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Prepares the final procurement result record."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "type": state.get("paper_type"),
                "gsm": state.get("gsm_weight"),
                "recycled_pct": state.get("recycled_content_pct"),
            },
            "status": state.get("availability_status"),
            "procurement_ready": state.get("availability_status") == "in_stock",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("check_inventory", check_inventory)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "check_inventory")
_g.add_edge("check_inventory", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
