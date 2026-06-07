# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101610 — Raw Material (segment 11).

This agent handles the lifecycle of raw materials, focusing on batch inspection,
purity verification, and inventory cataloging for industrial inputs.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101610"
UNISPSC_TITLE = "Raw Material"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101610"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Raw Material
    material_type: str
    purity_grade: float
    origin_batch_id: str
    inspection_status: str


def inspect_batch(state: State) -> dict[str, Any]:
    """Initial inspection of the raw material batch metadata."""
    inp = state.get("input") or {}
    material = inp.get("material_type", "unspecified")
    batch_id = inp.get("batch_id", "pending_assignment")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_batch:{batch_id}"],
        "material_type": material,
        "origin_batch_id": batch_id,
        "inspection_status": "in_progress"
    }


def verify_purity(state: State) -> dict[str, Any]:
    """Verification of the raw material purity grade against standards."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.0))

    # Simple threshold logic for purity certification
    status = "certified" if purity >= 0.95 else "substandard"

    return {
        "log": [f"{UNISPSC_CODE}:verify_purity:{status}"],
        "purity_grade": purity,
        "inspection_status": status
    }


def finalize_catalog(state: State) -> dict[str, Any]:
    """Finalizes the raw material entry for the inventory system."""
    status = state.get("inspection_status", "unknown")
    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalog"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "material_type": state.get("material_type"),
            "batch_id": state.get("origin_batch_id"),
            "purity": state.get("purity_grade"),
            "status": status,
            "ok": status == "certified",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_batch)
_g.add_node("verify", verify_purity)
_g.add_node("finalize", finalize_catalog)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
