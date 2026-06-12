# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101628 — Fork Procurement (segment 24).

Bespoke graph logic for handling the procurement lifecycle of industrial
forks, including specification validation, supplier selection, and
purchase order finalization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101628"
UNISPSC_TITLE = "Fork Procurement"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101628"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state for Fork Procurement
    fork_type: str
    load_capacity_lb: int
    supplier_selected: str
    compliance_certified: bool
    procurement_phase: str


def analyze_requisition(state: State) -> dict[str, Any]:
    """Validates the fork specifications and sets initial procurement phase."""
    inp = state.get("input") or {}
    fork_type = inp.get("fork_type", "Standard Taper")
    capacity = int(inp.get("capacity", 5000))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_requisition"],
        "fork_type": fork_type,
        "load_capacity_lb": capacity,
        "compliance_certified": capacity <= 15000,  # Example constraint
        "procurement_phase": "SPECIFICATION_LOCKED"
    }


def evaluate_vendors(state: State) -> dict[str, Any]:
    """Simulates supplier selection based on required load capacity."""
    capacity = state.get("load_capacity_lb", 0)

    if capacity > 10000:
        vendor = "HeavyDuty Forks & Attachments"
    else:
        vendor = "General Material Handling Corp"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_vendors"],
        "supplier_selected": vendor,
        "procurement_phase": "VENDOR_SELECTED"
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Generates the final procurement result and closes the agent cycle."""
    vendor = state.get("supplier_selected", "Internal Inventory")
    is_compliant = state.get("compliance_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "APPROVED" if is_compliant else "PENDING_REVIEW",
            "vendor": vendor,
            "spec": {
                "type": state.get("fork_type"),
                "capacity": state.get("load_capacity_lb")
            },
            "did": UNISPSC_DID,
            "ok": True,
        },
        "procurement_phase": "COMPLETED"
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_requisition)
_g.add_node("evaluate", evaluate_vendors)
_g.add_node("finalize", finalize_order)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
