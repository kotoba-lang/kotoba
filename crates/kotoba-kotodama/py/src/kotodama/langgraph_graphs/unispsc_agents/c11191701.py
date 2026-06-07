# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11191701 — Silicon Procurement (segment 11).

This bespoke agent handles the specialized logic for sourcing and verifying
high-purity silicon materials used in semiconductor manufacturing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11191701"
UNISPSC_TITLE = "Silicon Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11191701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Silicon Procurement
    purity_requirement: str  # e.g., "9N", "11N"
    wafer_diameter_mm: int   # e.g., 200, 300
    supplier_tier: int       # 1, 2, or 3
    is_certified: bool
    batch_tracking_code: str


def verify_specs(state: State) -> dict[str, Any]:
    """Validates the silicon purity and physical dimensions against standard grades."""
    inp = state.get("input") or {}
    purity = inp.get("purity", "9N")
    diameter = int(inp.get("diameter", 300))

    # Logic: Only accept 200mm or 300mm wafers for this agent
    valid_size = diameter in [200, 300]

    return {
        "log": [f"{UNISPSC_CODE}:verify_specs"],
        "purity_requirement": purity,
        "wafer_diameter_mm": diameter,
        "is_certified": valid_size
    }


def source_vendor(state: State) -> dict[str, Any]:
    """Identifies suitable silicon vendors based on purity requirements."""
    purity = state.get("purity_requirement", "9N")

    # High purity (11N) requires Tier 1 suppliers
    tier = 1 if purity == "11N" else 2

    return {
        "log": [f"{UNISPSC_CODE}:source_vendor"],
        "supplier_tier": tier,
        "batch_tracking_code": f"SIL-{tier}-{purity}-2026"
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final procurement record and metadata."""
    success = state.get("is_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_status": "authorized" if success else "rejected",
            "spec_summary": {
                "purity": state.get("purity_requirement"),
                "size": state.get("wafer_diameter_mm"),
                "batch": state.get("batch_tracking_code")
            },
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_specs", verify_specs)
_g.add_node("source_vendor", source_vendor)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "verify_specs")
_g.add_edge("verify_specs", "source_vendor")
_g.add_edge("source_vendor", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
