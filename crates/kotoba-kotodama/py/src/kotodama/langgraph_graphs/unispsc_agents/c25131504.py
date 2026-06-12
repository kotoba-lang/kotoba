# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131504 — Aircraft Procure (segment 25).

Bespoke graph logic for aircraft procurement workflows. This agent handles
specification validation, vendor auditing, and procurement execution for
aerospace assets.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131504"
UNISPSC_TITLE = "Aircraft Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Aircraft Procurement
    procurement_specs: dict[str, Any]
    vendor_selection: str
    budget_allocation: float
    regulatory_clearance: str


def validate_requirements(state: State) -> dict[str, Any]:
    """Ensures aircraft specifications and budget limits are defined."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {"type": "fixed-wing", "mission": "transport"})
    budget = inp.get("budget", 50000000.0)
    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "procurement_specs": specs,
        "budget_allocation": budget,
        "regulatory_clearance": "pending",
    }


def perform_vendor_audit(state: State) -> dict[str, Any]:
    """Selects and audits vendors based on aircraft type and mission."""
    specs = state.get("procurement_specs") or {}
    ac_type = specs.get("type", "fixed-wing")

    # Logic: Map aircraft type to a simulated preferred vendor
    vendor_map = {
        "fixed-wing": "Global Aero Systems",
        "rotary": "Vertical Lift Solutions",
        "uav": "Autonomous Flight Tech"
    }
    selected_vendor = vendor_map.get(ac_type, "Standard Aerospace Corp")

    return {
        "log": [f"{UNISPSC_CODE}:perform_vendor_audit"],
        "vendor_selection": selected_vendor,
        "regulatory_clearance": "authorized",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Constructs the final procurement record and status."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vendor": state.get("vendor_selection"),
            "specs": state.get("procurement_specs"),
            "clearance": state.get("regulatory_clearance"),
            "status": "order_placed",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("audit", perform_vendor_audit)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "audit")
_g.add_edge("audit", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
