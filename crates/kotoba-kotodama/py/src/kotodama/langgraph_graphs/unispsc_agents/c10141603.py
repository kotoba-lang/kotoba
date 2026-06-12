# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10141603 — Cattle (segment 10).

This agent provides bespoke logic for managing cattle livestock state,
including identification inspection, health certification, and quarantine
verification processes within the Etz Hayyim supply chain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10141603"
UNISPSC_TITLE = "Cattle"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10141603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Cattle (Live Animals)
    health_status: str
    transport_lot_id: str
    quarantine_verified: bool
    inspection_passed: bool


def inspect_livestock(state: State) -> dict[str, Any]:
    """
    Validates physical identification tags and performs initial health screening.
    """
    inp = state.get("input") or {}
    lot_id = inp.get("lot_id", "L-DEFAULT-99")

    # Heuristic: Cattle must have tag identification and weight records
    tags_present = inp.get("id_tags_present", True)
    weight_recorded = "weight_kg" in inp
    passed = tags_present and weight_recorded

    return {
        "log": [f"{UNISPSC_CODE}:inspect_livestock: lot {lot_id} (passed={passed})"],
        "transport_lot_id": lot_id,
        "inspection_passed": passed,
    }


def certify_health(state: State) -> dict[str, Any]:
    """
    Verifies quarantine duration and assigns a formal health certification status.
    """
    if not state.get("inspection_passed"):
        return {
            "log": [f"{UNISPSC_CODE}:certify_health: rejected due to failed inspection"],
            "health_status": "unverified",
            "quarantine_verified": False,
        }

    # Simulate quarantine logic
    inp = state.get("input") or {}
    days_in_iso = inp.get("quarantine_days", 0)
    verified = days_in_iso >= 14
    status = "certified_prime" if verified else "quarantine_pending"

    return {
        "log": [f"{UNISPSC_CODE}:certify_health: status={status}"],
        "health_status": status,
        "quarantine_verified": verified,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """
    Emits the final record for the cattle lot tracking state.
    """
    is_ok = state.get("quarantine_verified", False) and state.get("inspection_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record: final_ok={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "lot_id": state.get("transport_lot_id"),
            "health_certification": state.get("health_status"),
            "ready_for_transport": is_ok,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_livestock)
_g.add_node("certify", certify_health)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "certify")
_g.add_edge("certify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
