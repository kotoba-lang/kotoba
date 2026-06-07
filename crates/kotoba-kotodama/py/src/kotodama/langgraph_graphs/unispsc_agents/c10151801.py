# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151801 — Commodity (segment 10).

Bespoke graph logic for handling live animal commodity lifecycle and
transactional metadata within the Segment 10 livestock domain.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151801"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Live Animal Commodities
    health_status: str
    transport_lot_id: str
    quarantine_verified: bool
    market_valuation: float
    inspection_passed: bool


def validate_consignment(state: State) -> dict[str, Any]:
    """Validates the incoming commodity consignment data and lot identification."""
    inp = state.get("input") or {}
    lot_id = inp.get("lot_id", "LOT-TEMP-10151801")

    return {
        "log": [f"{UNISPSC_CODE}:validate_consignment"],
        "transport_lot_id": lot_id,
        "quarantine_verified": inp.get("quarantine", False),
        "inspection_passed": inp.get("inspection", False)
    }


def evaluate_market_readiness(state: State) -> dict[str, Any]:
    """Assesses the health and readiness of the animal commodity for trade."""
    is_ready = state.get("quarantine_verified", False) and state.get("inspection_passed", False)
    status = "CERTIFIED_READY" if is_ready else "PENDING_CLEARANCE"

    # Simple logic to determine market value based on readiness
    valuation = 2500.0 if is_ready else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_market_readiness"],
        "health_status": status,
        "market_valuation": valuation
    }


def finalize_commodity_record(state: State) -> dict[str, Any]:
    """Compiles the final transaction-ready record for the livestock agent."""
    is_ready = state.get("health_status") == "CERTIFIED_READY"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_commodity_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "lot_id": state.get("transport_lot_id"),
            "health_certificate": state.get("health_status"),
            "valuation_estimate": state.get("market_valuation"),
            "transaction_authorized": is_ready,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_consignment)
_g.add_node("evaluate", evaluate_market_readiness)
_g.add_node("finalize", finalize_commodity_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
