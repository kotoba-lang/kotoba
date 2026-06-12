# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131903 — Helicopter Procurement (segment 25).

Bespoke logic for managing helicopter procurement workflows, including
requirement validation, budget verification, and vendor selection processing.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131903"
UNISPSC_TITLE = "Helicopter Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for helicopter procurement
    procurement_phase: str
    specifications_cleared: bool
    funding_token: str
    candidate_vendors: list[str]


def analyze_specifications(state: State) -> dict[str, Any]:
    """Analyzes the technical specifications for the helicopter procurement."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})
    # Check for basic aviation metrics
    is_valid = all(k in specs for k in ["lift_capacity", "service_ceiling", "rotor_type"])

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications"],
        "specifications_cleared": is_valid,
        "procurement_phase": "SPEC_ANALYSIS"
    }


def verify_funding(state: State) -> dict[str, Any]:
    """Verifies that the procurement has been allocated appropriate funding."""
    inp = state.get("input") or {}
    budget = inp.get("budget", 0)
    token = f"FUND-{UNISPSC_CODE}-2026-OK" if budget > 500000 else "FUND-INSUFFICIENT"

    return {
        "log": [f"{UNISPSC_CODE}:verify_funding"],
        "funding_token": token,
        "procurement_phase": "FUNDING_VERIFICATION"
    }


def evaluate_vendors(state: State) -> dict[str, Any]:
    """Evaluates the list of potential helicopter manufacturers or suppliers."""
    inp = state.get("input") or {}
    vendors = inp.get("vendors", []) or []
    # Filter or process vendor list (mock logic)
    shortlist = [v for v in vendors if isinstance(v, dict) and v.get("certified", False)]

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_vendors"],
        "candidate_vendors": [v.get("name", "Unknown") for v in shortlist],
        "procurement_phase": "VENDOR_EVALUATION"
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Aggregates state and emits the final procurement recommendation."""
    ready = state.get("specifications_cleared", False) and "OK" in state.get("funding_token", "")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "procurement_phase": "COMPLETED",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "authorized": ready,
            "summary": {
                "vendors_qualified": len(state.get("candidate_vendors", [])),
                "phase": state.get("procurement_phase")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("spec_check", analyze_specifications)
_g.add_node("funding_check", verify_funding)
_g.add_node("vendor_check", evaluate_vendors)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "spec_check")
_g.add_edge("spec_check", "funding_check")
_g.add_edge("funding_check", "vendor_check")
_g.add_edge("vendor_check", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
