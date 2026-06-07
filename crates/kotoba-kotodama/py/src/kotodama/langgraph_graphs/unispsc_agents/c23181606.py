# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181606 — Laser Procurement (segment 23).
Bespoke logic for industrial and scientific laser acquisition workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181606"
UNISPSC_TITLE = "Laser Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Laser Procurement
    specs_verified: bool
    safety_standards_met: bool
    supplier_id: str
    budget_limit: float


def validate_requirements(state: State) -> dict[str, Any]:
    """Ensures technical specifications and power ratings are provided."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})
    power_watt = specs.get("power_watt", 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "specs_verified": power_watt > 0,
        "supplier_id": inp.get("preferred_supplier", "GENERIC_OPTICS_01"),
    }


def assess_compliance(state: State) -> dict[str, Any]:
    """Checks for FDA/IEC laser safety class compliance based on power."""
    inp = state.get("input") or {}
    power = inp.get("specifications", {}).get("power_watt", 0)

    # Higher power lasers (>500mW) require stricter certification flags
    compliance = True if power < 500 else inp.get("safety_cert_provided", False)

    return {
        "log": [f"{UNISPSC_CODE}:assess_compliance"],
        "safety_standards_met": compliance,
        "budget_limit": float(inp.get("budget", 10000.0)),
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Constructs the final procurement authorization or rejection."""
    ready = state.get("specs_verified") and state.get("safety_standards_met")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "APPROVED" if ready else "REJECTED_INCOMPLETE_SAFETY",
            "supplier": state.get("supplier_id"),
            "authorized_limit": state.get("budget_limit"),
            "execution_cycle": "2026-Q2",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_requirements", validate_requirements)
_g.add_node("assess_compliance", assess_compliance)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_requirements")
_g.add_edge("validate_requirements", "assess_compliance")
_g.add_edge("assess_compliance", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
