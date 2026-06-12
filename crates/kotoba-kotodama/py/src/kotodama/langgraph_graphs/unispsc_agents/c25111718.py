# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111718 — Vessel Procurement (segment 25).

Bespoke graph logic for procurement of commercial and industrial vessels.
This implementation handles specification validation, vendor tender evaluation,
and final procurement authorization for maritime assets.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111718"
UNISPSC_TITLE = "Vessel Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111718"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Vessel Procurement Domain Fields
    vessel_specification: dict[str, Any]
    vendor_bids: list[dict[str, Any]]
    procurement_phase: str
    budget_approved: bool


def validate_vessel_specs(state: State) -> dict[str, Any]:
    """Validate technical specifications for the vessel procurement request."""
    inp = state.get("input") or {}
    specs = inp.get("specs") or {}

    # Check for core requirements like tonnage and vessel class
    has_tonnage = "deadweight_tonnage" in specs
    has_type = "vessel_type" in specs
    is_valid = has_tonnage and has_type

    # Basic budget sanity check
    estimated_cost = specs.get("estimated_cost", 0)
    budget_ok = estimated_cost > 0 and estimated_cost < 1_000_000_000

    return {
        "log": [f"{UNISPSC_CODE}:validate_vessel_specs"],
        "vessel_specification": specs,
        "procurement_phase": "specification_validated" if is_valid else "specification_invalid",
        "budget_approved": budget_ok,
    }


def evaluate_tender_bids(state: State) -> dict[str, Any]:
    """Evaluate submitted bids from qualified maritime vendors based on specs."""
    specs = state.get("vessel_specification") or {}
    base_cost = specs.get("estimated_cost", 1000000)

    # Simulate bid selection from a pool of registered shipyards
    mock_bids = [
        {"vendor": "Global Maritime Heavy Industries", "bid_amount": base_cost * 0.98, "delivery_weeks": 52},
        {"vendor": "Pacific Shipwrights Group", "bid_amount": base_cost * 1.02, "delivery_weeks": 40},
    ]

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_tender_bids"],
        "vendor_bids": mock_bids,
        "procurement_phase": "tendering_complete",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalize the procurement contract and emit the formal result."""
    bids = state.get("vendor_bids") or []
    budget_ok = state.get("budget_approved", False)
    phase = state.get("procurement_phase")

    # Award to lowest bidder if budget is approved and specs were valid
    can_award = budget_ok and phase == "tendering_complete" and len(bids) > 0
    winning_bid = min(bids, key=lambda x: x["bid_amount"]) if can_award else None

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "contract_awarded" if winning_bid else "procurement_aborted",
            "awardee": winning_bid["vendor"] if winning_bid else None,
            "contract_value": winning_bid["bid_amount"] if winning_bid else 0,
            "ok": bool(winning_bid),
        },
    }


_g = StateGraph(State)
_g.add_node("validate_vessel_specs", validate_vessel_specs)
_g.add_node("evaluate_tender_bids", evaluate_tender_bids)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_vessel_specs")
_g.add_edge("validate_vessel_specs", "evaluate_tender_bids")
_g.add_edge("evaluate_tender_bids", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
