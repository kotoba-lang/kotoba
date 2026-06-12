# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151601 — Commodity (segment 10).
Bespoke implementation for live material commodity lifecycle management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151601"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151601"


class State(TypedDict, total=False):
    # Fundamental agent state
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Commodity (Live Plant/Animal Material)
    lot_identifier: str
    origin_certificate_id: str
    quarantine_verified: bool
    biological_safety_score: float
    market_ready: bool


def manifest_intake(state: State) -> dict[str, Any]:
    """Parses the incoming manifest and assigns internal lot tracking."""
    inp = state.get("input") or {}
    lot_id = inp.get("lot_id", f"LOT-{UNISPSC_CODE}-DEFAULT")
    origin = inp.get("origin_id", "CERT-PENDING")

    return {
        "log": [f"{UNISPSC_CODE}:manifest_intake (lot={lot_id})"],
        "lot_identifier": lot_id,
        "origin_certificate_id": origin,
    }


def safety_inspection(state: State) -> dict[str, Any]:
    """Simulates biological safety checks for the live material commodity."""
    # Logic: Certain certificate prefixes imply higher safety scores
    cert = state.get("origin_certificate_id", "")
    is_verified = cert.startswith("CERT-VA")
    score = 0.95 if is_verified else 0.45

    return {
        "log": [f"{UNISPSC_CODE}:safety_inspection (score={score})"],
        "quarantine_verified": is_verified,
        "biological_safety_score": score,
    }


def certify_market_readiness(state: State) -> dict[str, Any]:
    """Finalizes the commodity state based on inspection results."""
    score = state.get("biological_safety_score", 0.0)
    is_ready = score > 0.70

    return {
        "log": [f"{UNISPSC_CODE}:certify_market_readiness (ready={is_ready})"],
        "market_ready": is_ready,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "lot_id": state.get("lot_identifier"),
            "status": "APPROVED" if is_ready else "REJECTED_OR_HELD",
            "safety_score": score,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("intake", manifest_intake)
_g.add_node("inspect", safety_inspection)
_g.add_node("certify", certify_market_readiness)

_g.add_edge(START, "intake")
_g.add_edge("intake", "inspect")
_g.add_edge("inspect", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
